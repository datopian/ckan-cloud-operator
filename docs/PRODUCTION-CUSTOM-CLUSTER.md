# Creating a Production CKAN Cloud cluster using a custom / self-hosted provider

## Prerequisites

* Custom Provider values, check the custom provider docs for details
    * e.g. `https://github.com/OriHoch/cco-provider-kamatera/blob/master/README.md`
* An external domain
* A CKAN Cloud Operator [working environment](./WORKING-ENVIRONMENT.md)

## Provision the cluster

Check the custom provider docs for creating the cluster.

Once the cluster was created on the custom provider, you can continue initializing ckan-cloud-operator: 

```
CCO_INTERACTIVE_CI=/path/to/interactive.yaml \
    ckan-cloud-operator cluster initialize --cluster-provider=PROVIDER_NAME
```
