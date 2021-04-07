This repo contains a controller automatically labelling nodes based on either:

- predefined regex rules matching node name.
- a set of matching labels (with their associated value) present on the node.

Furthermore, an additional controller for autosigning certs using regex rules is provided for use in Openshift.


## Configuration

A configmap named needs to be created to define rules. 

For instance, you can use the following:

```
NAMESPACE="default"
kubectl create configmap -n $NAMESPACE autorules --from-file=rules1.properties --from-file=rules2.properties
```

### Name based rules

Rule is indicated as a regex matching the node name, and a list of labels to add (either a string or a dict entry):

```
name: .*prod-worker.*
labels:
- node-role.kubernetes.io/megaprod
- competent: indeed
```

Additionally, the field `runonce` can be set to true to only label matching nodes the first time, and then stop handling labels (this is accomplished by using the extra label autolabelled and skipping the nodes that have it)


### Matching label based rules

Rule is indicated as a list of matchlabels to be found in the node matching, and a list of labels to add:

```
matchlabels:
- node-role.kubernetes.io/masterx
- node-role.kubernetes.io/mastery
labels:
- node-role.kubernetes.io/mastermind
```

### Allowing specific networks

An optional list of allowed networks can be specified for the autosigner controller using the following syntax: 

```
allowed_networks:
- 192.168.122.0/24
- 192.168.123.0/24
```

If this list is not empty, only csrs of nodes reporting an ip from one of the ranges (in their SAN section) can be signed.


### Using a specific configmap or specific namespace

- The name of the config map to use can be specified with the CONFIG_MAP env variable. It defaults to `autorules` if the variable is not found.
- The namespace from where autolabeller deployment runs is used to gather the configmap, otherwise one can use the NAMESPACE env variable when running in standalone mode. It defaults to `default` if the variable is not found.

## Running

### dev mode

You will need python3 and [kubernetes client python](https://github.com/kubernetes-client/python) that you can either install with pip or your favorite package manager. Then, provided you have set your KUBECONFIG environment variable, just run:

```
SCRIPT="autolabeller.py"
python3 $SCRIPT
```

NOTE: use the `autosigner.py` script in the same way

### standalone mode

You can run against an existing cluster after setting your KUBECONFIG env variable with the following invocation

```
IMAGE="karmab/autolabeller"
podman run -v $(dirname $KUBECONFIG):/kubeconfig -e KUBECONFIG=/kubeconfig/kubeconfig --rm -it karmab/autolabeller
```

Note: use a similar approach with `karmab/autosigner` image

### On Openshift/Kubernetes

#### Signer

```
NAMESPACE="default"
kubectl create clusterrolebinding autolabeller-admin-binding --clusterrole=cluster-admin --serviceaccount=$NAMESPACE:default --namespace=$NAMESPACE
kubectl create -f signer.yml -f $NAMESPACE
```

#### Labeller

```
NAMESPACE="default"
kubectl create clusterrolebinding autolabeller-admin-binding --clusterrole=cluster-admin --serviceaccount=$NAMESPACE:default --namespace=$NAMESPACE
kubectl create -f labeller.yml -f $NAMESPACE
```

#### Everything

The following command will create:

- the `autorules` namespace
- a sample configmap for signing any *worker* node and labelling them as such
- a clusterrole binding giving cluster-admin to default service account in the autorules namespace
- a deployment with autolabeller pod

```
kubectl create -f autorules.yml
```

On openshift, you can deploy the same plus the extra autosigner with the following, which simply adds the autosigner container to the deployment pod

```
oc create -f autorules_openshift.yml
```
