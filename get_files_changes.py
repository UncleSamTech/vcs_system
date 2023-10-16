#from parsers.max.maxparser import MalformedMaxMSP
#from parsers.max.maxparser import main as maxparser

from pydriller import ModificationType
from pydriller.repository import Repository
from pydriller.git import Git

from pathlib import Path
import os
from statistics import mean
from datetime import datetime
import math
from deepdiff import DeepDiff
import re

import pandas as pd

#import typer
import tempfile
import subprocess
import pickle
import json

class file_renames:

    def __init__(self):
        self.maybe_sha = None
        self.all_sha_names = {}
        self.all_sha_dates = {}
        self.list_response = []
        self.prev_intermediate_format = {}
        self.all_shas = None
        self.complete_branch = None
        self.stat_contents = {}
        self.val_diff = None
        self.project_names = []
        self.scratch_json_response = ''
        

    
    def is_sha1(self,maybe_sha):
        if len(maybe_sha) != 40:
            return False
        try:
            sha_int = int(maybe_sha, 16)
        except ValueError:
            return False
        return True
    

    def get_file_renames_contents(self,cwd, main_branch, project_name, debug=False):

        proc1 = subprocess.run(['git --no-pager log --pretty=tformat:"%H" {} --no-merges'.format(main_branch)],stdout=subprocess.PIPE, cwd=cwd, shell=True)
    
        proc2 = subprocess.run(['xargs -I{} git ls-tree -r --name-only {}'], input=proc1.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
        
        proc3 = subprocess.run(['grep -i ".sb3$\|.sb2$"'], input=proc2.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
        
        proc4 = subprocess.run(['sort -u'], input=proc3.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)

        
        filenames = proc4.stdout.decode().strip().split('\n')
        
        for f in filenames:
            proc1 = subprocess.run(['git --no-pager log -z --numstat --follow --pretty=tformat:"{}¬%H" -- "{}"'.format(f,f)], stdout=subprocess.PIPE, cwd=cwd, shell=True)
            proc2 = subprocess.run(["cut -f3"], input=proc1.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
            proc3 = subprocess.run(["sed 's/\d0/¬/g'"], input=proc2.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
            proc4 = subprocess.run(['xargs -0 echo'], input=proc3.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
            filename_shas = proc4.stdout.decode().strip().split('\n')
            filename_shas = [x for x in filename_shas if x != '']
            proc1 = subprocess.run(['git --no-pager log --all --pretty=tformat:"%H" -- "{}"'.format(f)], stdout=subprocess.PIPE, cwd=cwd, shell=True) # Does not produce renames
            self.all_shas = proc1.stdout.decode().strip().split('\n') 
            self.all_shas = [x for x in self.all_shas if x != '']
            
            for x in self.all_shas:
                self.all_sha_names[x] = None

            
            # get filenames for each commit
            for fn in filename_shas: # start reversed, oldest to newest
                separator_count = fn.strip().count('¬')
                split_line = fn.strip('¬').split('¬')
                # print(split_line)
                file_contents = ''

                if separator_count == 2:
                    c = split_line[-1]
                
                    if not self.is_sha1(c):
                    # Edge case where line doesn't have a sha
                        print(split_line)
                        continue

                    self.all_sha_names[c] = split_line[0]
                    #print('shaids1',self.all_sha_names)
                
                elif fn[0] == '¬':
                    new_name = split_line[0]
                    c = split_line[-1]

                    if not self.is_sha1(c):
                    # Edge case where line doesn't have a sha
                        print(split_line)
                        continue

                    self.all_sha_names[c] = split_line[-2] 
                    print('shaids2',self.all_sha_names)

                elif separator_count == 3:
                    # print(split_line[-1])
                    new_name = split_line[0]
                    c = split_line[-1]
                
                    if not self.is_sha1(c):
                    # Edge case where line doesn't have a sha
                        print(split_line)
                        continue
                    
                    self.all_sha_names[c] = split_line[-2]
                    print('shaids3',self.all_sha_names)
                elif separator_count == 1:
                    continue
        
                else:
                    raise ValueError('Unknown case for file')
            
            for c in self.all_sha_names.keys():
                
                commit_date = subprocess.run(['git log -1 --format=%ci {}'.format(c)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd, shell=True).stdout.decode()
                
                if commit_date == '':
                    continue 
                    
                parsed_date = datetime.strptime(commit_date.strip(), '%Y-%m-%d %H:%M:%S %z')
                
                parsed_date_str = parsed_date.strftime('%Y-%m-%d %H:%M:%S %z')
                
                self.all_sha_dates[c] = parsed_date
                          
            # fill in the gaps
            prev_fn = f
            for c in self.all_sha_names.keys():
                if self.all_sha_names[c] is None:
                    self.all_sha_names[c] = prev_fn
                prev_fn = self.all_sha_names[c]


            
            for c in sorted(self.all_sha_dates, key=self.all_sha_dates.get): # start oldest to newest
                new_name = self.all_sha_names[c]

                file_contents = ''

                file_contents = subprocess.run(['git show {}:"{}"'.format(c, new_name)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd, shell=True).stdout.decode("utf-8", "ignore")
                                
                commit_date = subprocess.run(['git log -1 --format=%ci {}'.format(c)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd, shell=True).stdout.decode()

                if commit_date == '':
                    continue
             
                parsed_date = datetime.strptime(commit_date.strip(), '%Y-%m-%d %H:%M:%S %z')

                if parsed_date == '':
                    continue

               
                # Parse the code into intermediate representation
                with tempfile.NamedTemporaryFile(dir=os.getcwd()+'/sb3tempfiles',delete=False) as fp:
                    fp.write(file_contents.encode())
                    
                    self.stat_contents["commit_sha"] = c
                    self.stat_contents["commit_date"] = parsed_date_str
                    self.stat_contents["file_name"] = new_name
                    self.stat_contents["file_contents"] = fp.name
                os.remove(fp.name)
        
                self.scratch_json_response = json.dumps(self.stat_contents,indent=4)

                name1 = subprocess.run(["echo {}".format(new_name)], stdout=subprocess.PIPE, cwd=cwd, shell=True)
                
                name2 = subprocess.run(["sed 's/\.[^.]*$//'"], input=name1.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
                
                name3 = subprocess.run(["sed 's/\//\_FOLDER_/g'"], input=name2.stdout, stdout=subprocess.PIPE, cwd=cwd, shell=True)
                
                new_json_file_name = name3.stdout.decode().strip()

                with open('/home/siwuchuk/sb3revisions_details/'  + project_name + '/' + new_json_file_name + '.json', 'w') as f:
                    f.write(self.scratch_json_response)

       
    
    def main(self,proj_path):
        for i in os.listdir(proj_path):
            self.project_names.append(i.strip('\n'))
        for proj_name in self.project_names:
            print('proj_name',proj_name)
            self.complete_branch = proj_path + proj_name.strip('\n') 
            main_branch = subprocess.run(['git rev-parse --abbrev-ref HEAD'], stdout=subprocess.PIPE, cwd=self.complete_branch, shell=True) 
            self.val_diff = self.get_file_renames_contents(self.complete_branch,main_branch.stdout.decode("utf-8").strip('/n')[0:],proj_name.strip('\n'))
         
        return self.val_diff
                
                
val_class = file_renames()

val_class.main('/home/siwuchuk/sb3projects/')



