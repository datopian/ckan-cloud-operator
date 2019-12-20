helm init
sleep 10
helm repo update
slee 20
helm install --namespace=ckan-cloud stable/nfs-server-provisioner --name cloud-nfs --set=persistence.enabled=true,persistence.size=500Gi,storageClass.name=cca-ckan
sleep 200
kubectl create -f cca-storage.yaml
