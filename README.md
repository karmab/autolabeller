This repo contains a sample controller automatically labelling nodes based on either:
- predefined regex rules matching node name.
- a set of matching labels already present in the node

## Configuration

A configmap named needs to be created to define rules. For instance, you can use the following:

```
NAMESPACE="default"
kubectl create configmap -n $NAMESPACE labelrules --from-file=rules1.properties --from-file=rules2.properties
```

### Name based rules

Rule is indicated as a regex matching the node name, and a list of labels to add.

```
name: .*prod-worker.*
labels:
- node-role.kubernetes.io/megaprod
- ptp/master
```

### Matching label based rules

Rule is indicated as a list of matchlabels to be found in the node matching, and a list of labels to add.

```
matchlabels:
- node-role.kubernetes.io/masterx
- node-role.kubernetes.io/mastery
labels:
- node-role.kubernetes.io/mindmaster
```

### Using a specific configmap or specific namespace

- The name of the config map to use can be specified with the CONFIG_MAP env variable. It defaults to `labelrules` if the variable is not found.
- The namespace from where autolabeller deployment runs is used to gather the configmap, otherwise one can use the NAMESPACE env variable when running in standalone mode. It defaults to `default` if the variable is not found.


## Running

### dev mode

You will need python3 and [kubernetes client python](https://github.com/kubernetes-client/python) that you can either install with pip or your favorite package manager. Then, provided you have set your KUBECONFIG environment variable, just run:

```
python3 controller.py
```

### standalone mode

You can run against an existing cluster after setting your KUBECONFIG env variable with the following invocation

```
podman run -v $(dirname $KUBECONFIG):/kubeconfig -e KUBECONFIG=/kubeconfig/kubeconfig --rm -it karmab/autolabeller
```

### Within a running cluster

#### On Kubernetes

```
NAMESPACE="default"
kubectl create clusterrolebinding autolabeller-admin-binding --clusterrole=cluster-admin --serviceaccount=$NAMESPACE:default --namespace=$NAMESPACE
kubectl create -f deployment.yaml -n $NAMESPACE
```

#### On Openshift

```
NAMESPACE="default"
oc adm policy add-cluster-role-to-user cluster-admin -z default -n $NAMESPACE
oc new-app karmab/autolabeller -n $NAMESPACE
```
