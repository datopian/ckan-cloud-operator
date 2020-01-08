import json
import os

template = {
    "installationId": os.environ.get('AZ_TEST_installationId'),
    "subscriptions": [
        {
        "id": os.environ.get('AZ_TEST_id'),
        "name": "Datopian",
        "state": "Enabled",
        "user": {
            "name": os.environ.get('AZ_TEST_email'),
            "type": "user"
        },
        "isDefault": True,
        "tenantId": os.environ.get('AZ_TEST_tenantId'),
        "environmentName": "AzureCloud"
        }
    ]
}

with open(os.path.expanduser('~/.azure/azureProfile.json'), 'w') as outfile:
    json.dump(template, outfile)

print('success')
