# Node management DaemonSet

This container is meant to run as a DaemonSet on each node in the cluster.

It can be used to set or monitor the cluster nodes.

## Set SSH keys for ec2 cluster nodes

Mount the following volumes on the DaemonSet:

* `/home/ec2-user` - hostPath to the same directory in the node
* `/ec2-user-authorized-keys` - a secret with each entry containing a public SSH key file to add
 