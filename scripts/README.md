# ckan-cloud-operator scripts

misc. scripts which are typically executed from an automation app like Jenkins.

## Running scripts from automation tools

Set the required operator version:

```
CKAN_CLOUD_OPERATOR_VERSION="v0.2.2"
```

Set the script name and extension:

```
SCRIPT_NAME="configuration and secrets management"
SCRIPT_EXT="sh"
```

Check the script file for required env vars, for example:

```
export ACTION=get
export ARGS="--namespace ckan-cloud"
```

Run the script:

```
curl -L "https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-operator/${CKAN_CLOUD_OPERATOR_VERSION}/scripts/$(echo "$SCRIPT_NAME" | sed 's/ /%20/g').${SCRIPT_EXT}" \
  | tee /dev/stderr \
  | if [ "${SCRIPT_EXT}" == "py" ]; then python3; else bash; fi
```

## Jenkins integration

* Set job name the same as a script name
* Define the args as parameters for the job

For .sh scripts:

```
export CKAN_CLOUD_OPERATOR_VERSION="v0.2.2"
curl -L "https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-operator/${CKAN_CLOUD_OPERATOR_VERSION}/scripts/$(echo "$JOB_NAME" | sed 's/ /%20/g').sh" \
  | tee /dev/stderr | bash
```

For .py scripts:

```
export CKAN_CLOUD_OPERATOR_VERSION="v0.2.2"
curl -L "https://raw.githubusercontent.com/ViderumGlobal/ckan-cloud-operator/${CKAN_CLOUD_OPERATOR_VERSION}/scripts/$(echo "$JOB_NAME" | sed 's/ /%20/g').py" \
  | tee /dev/stderr | python3
```
