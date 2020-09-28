This repo contains a sample controller automatically labelling nodes based on predefined rules

## Configuration

A predefined configmap named `labelrules` needs to be created in *default* namespace. For instance, you can use the following:

```
kubectl create configmap -n default labelrules --from-file=rules1.properties --from-file=rules2.properties
```

The rule file has the following format:

```
rule: .*master.*
labels:
- node-role.kubernetes.io/supermaster
```

That is, rule is indicated as a regex matching the node name, and a list of labels will be added (on top of the existing ones for the node)

## Running

### For development/testing

You can run against an existing cluster after setting your KUBECONFIG env variable with the following invocation

```
podman run -v $(dirname $KUBECONFIG):/kubeconfig -e KUBECONFIG=/kubeconfig/kubeconfig --rm -it karmab/autolabeller
```

### Within a running cluster

#### On Kubernetes

```
kubectl create clusterrolebinding autolabeller-admin-binding --clusterrole=cluster-admin --serviceaccount=default:default --namespace=default
kubectl create -f deployment.yaml -n default
```

#### On Openshift

```
oc adm policy add-cluster-role-to-user cluster-admin -z default -n default
oc new-app karmab/autolabeller -n default
```
