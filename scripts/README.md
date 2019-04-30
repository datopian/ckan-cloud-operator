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
* Source code management: git
  * repository url: https://github.com/ViderumGlobal/ckan-cloud-operator.git
  * branch specifier: `master` (or required commit / tag)
* Execute shell scripts:
  * For .sh scripts:
    `bash "scripts/${JOB_NAME}.sh"`
  * For .py scripts:
    `python3 "scripts/${JOB_NAME}.py"`

If you made changes to ckan-cloud-operator which the script depends on, you can update it with `python3 -m pip install -t /home/jenkins/ckan-cloud-operator --upgrade .`.
Bear in mind it updates the package to all jobs on the node

Use the following snippet for upgrading the operator + redirecting error logs properly:

```
python3 -m pip install -t /home/jenkins/ckan-cloud-operator --upgrade . >/dev/null 2>&1 &&\
python3 "scripts/${JOB_NAME}.py" 2>stderr.log
[ "$?" != "0" ] && cat stderr.log && exit 1
exit 0
```
