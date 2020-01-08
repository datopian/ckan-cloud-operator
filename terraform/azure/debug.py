import json
import os
import codecs

prof = json.loads(codecs.open(os.path.expanduser('~/.azure/azureProfile.json'), 'r', 'utf-8-sig').read())
print('========================================')
print(prof.get('subscriptions', [{}])[0].get('id', '1234')[-4:])
