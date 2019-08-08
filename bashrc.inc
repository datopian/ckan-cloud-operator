conda activate ckan-cloud-operator
if [ -z "$NO_KUBE_CONFIG" ]; then
    [ -e /etc/ckan-cloud/.kube-config ] && export KUBECONFIG=/etc/ckan-cloud/.kube-config
    ! [ -z "${KUBE_CONTEXT}" ] && kubectl config use-context "${KUBE_CONTEXT}" >/dev/null 2>&1
    ! [ "$(ckan-cloud-operator config get --key=ckan-cloud-provider-cluster-main-provider-id --raw)" == "aws" ] && ckan-cloud-operator activate-gcloud-auth >/dev/null 2>&1
    ckan-cloud-operator db proxy port-forward --all-daemon "I know the risks" >/dev/null 2>&1
    while ! pg_isready -h localhost >/dev/null 2>&1; do sleep .1; done
fi
