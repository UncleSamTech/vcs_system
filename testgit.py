import os
from pydriller import Git

def quick_drill():

    with open('files_test/quicktest.txt') as f:
      for files in f:
         #print(files)
         values = files.split('/')[1]
         print(values)
    
    #git_object = Git(f'Scratch')
    #git_object.checkout('main')

    #print('files',git_object.files())

quick_drill()