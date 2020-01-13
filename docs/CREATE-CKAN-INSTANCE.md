# Create a CKAN Instance

This short tutorial will guide you in creating a CKAN instance on the cluster.

First make sure you have a CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md).

Then, use CCO's CLI to create the instance:

```bash
$ ckan-cloud-operator ckan instance create helm --instance-id a-ckan-instance --instance-name a-ckan-instance --update <values.yaml>
```
The `ckan instance create helm` accepts the following parameters:

- `--instance-id` - a unique identifier for this instance
- `--instance-name` - a non-unique identifier for this instance (you can use the same value as the instance-id)
- `--update` - adding this option will create the instance metadata and update (apply) it in the cluster.
  
  If `--update` is not provided, you would need to call the `ckan instance update` command manually on your own.
- `<values.yaml>` - the filename of the values file containing the specification for the CKAN instance to be created.
  
  Check out the [values file reference](./VALUES-FILE-REFERENCE.md) for details.
  