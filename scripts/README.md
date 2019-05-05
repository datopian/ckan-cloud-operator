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

### Create job

* Set job name the same as a script name
* Define the args as parameters for the job

Use the following snippet to run a script from the installed operator version + redirecting error logs properly:

For .py scripts:

```
python3 "${CKAN_CLOUD_OPERATOR_SCRIPTS}/${JOB_NAME}.py"
```

For .sh scripts:

```
bash "${CKAN_CLOUD_OPERATOR_SCRIPTS}/${JOB_NAME}.sh"
```

To test development version of the scripts, you can just copy-paste the script to a Jenkins execute shell step

Alternatively, to test a committed script, add the following to the job configuration: 

* Source code management: git
  * repository url: https://github.com/ViderumGlobal/ckan-cloud-operator.git
  * branch specifier: `master` (or required commit / tag)

Append the following snippet before the last run snippet:

```
CKAN_CLOUD_OPERATOR_SCRIPTS=`pwd`/scripts
```

If you made changes to the ckan-cloud-operator code which the script depends on, you can update it with the following snippet.

Bear in mind it updates the ckan-cloud-operator Python package for all jobs on the node, so you should only upgrade with backwards compatible changes.

Add the following snippet before the run snippet:

```
python3 -m pip install . &&\
```

### trigger other jobs

* Script should create an env file containing KEY=VALUE per line corresponding to the triggered job parameters
* Add post-build actions:
  * Archive file artifacts:
    * Files to archive: relative path to the created env file
  * Trigger parameterized build on other projects
    * Builld triggers:
      * projects to build: name of job to trigger
      * trigger when build is stable
      * parameters from properties file:
        * use properties from file: name of the created env file
        * don't trigger if any files are missing: check
