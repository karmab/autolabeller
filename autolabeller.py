import yaml
from kubernetes import client, config, watch
import os
import re


if __name__ == "__main__":
    if 'KUBERNETES_PORT' in os.environ:
        config.load_incluster_config()
    else:
        config.load_kube_config()
    configuration = client.Configuration()
    configuration.assert_hostname = False
    api_client = client.api_client.ApiClient(configuration=configuration)
    v1 = client.CoreV1Api()
    try:
        k8sfile = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
        namespace = open(k8sfile, 'r').read() if os.path.exists(k8sfile) else os.environ.get('NAMESPACE', 'default')
        config_map_name = os.environ.get('CONFIG_MAP', 'autorules')
        config_map = v1.read_namespaced_config_map(namespace=namespace, name=config_map_name)
        config_map_data = config_map.to_dict().get('data', {})
    except Exception as e:
        if e.status == 404:
            print("Missing configmap %s in namespace %s" % (config_map_name, namespace))
        else:
            print(e)
        print("No rules defined, using default worker one")
        config_map_data = {'rules1.properties': 'name: .*worker.*\nlabels:\n- node-role.kubernetes.io/worker=\n'}
    name_rules = {}
    label_rules = {}
    if not config_map_data:
        print("No rules defined, using default worker one")
        config_map_data = {'rules1.properties': 'name: .*worker.*\nlabels:\n- node-role.kubernetes.io/worker=\n'}
    for entry in config_map_data:
        try:
            data = yaml.safe_load(config_map_data[entry])
        except yaml.scanner.ScannerError as err:
            print("Incorrect configmap. Leaving")
            os._exit(1)
        newname, newmatchlabels, newlabels = data.get('name'), data.get('matchlabels'), data.get('labels')
        if newlabels is None:
            print("No valid labels found in rule %s.Ignoring" % entry)
            continue
        else:
            goodlabels = {}
            for label in newlabels:
                if isinstance(label, str):
                    goodlabels[label] = ''
                elif isinstance(label, dict):
                    for k in label:
                        goodlabels[k] = label[k]
        if newname is not None:
            print("Handling name rule %s with labels %s" % (newname, goodlabels))
            name_rules[newname] = goodlabels
        if newmatchlabels is not None:
            print("Handling matchlabels rule %s with labels %s" % (newmatchlabels, goodlabels))
            matchlabels = []
            for x in newmatchlabels:
                if isinstance(x, str):
                    matchlabels.append({x: ""})
                elif isinstance(x, dict):
                    matchlabels.append(x)
            label_rules[entry] = {'matchlabels': matchlabels, 'labels': goodlabels}
    print("Starting main labeller loop...")
    while True:
        stream = watch.Watch().stream(v1.list_node, timeout_seconds=10)
        for event in stream:
            obj = event["object"]
            obj_dict = obj.to_dict()
            node_name = obj_dict['metadata']['name']
            node_labels = obj_dict['metadata']['labels']
            add_labels = {}
            for name in name_rules:
                if re.match(name, node_name):
                    add_labels.update(name_rules[name])
            mismatch = False
            for entry in label_rules:
                matchlabels = label_rules[entry]['matchlabels']
                for label in matchlabels:
                    labelkey = list(label)[0]
                    if labelkey not in node_labels or label[labelkey] != node_labels[labelkey]:
                        mismatch = True
                        break
                if not mismatch:
                    add_labels.update(label_rules[entry]['labels'])
            if add_labels:
                missing_labels = {label: add_labels[label] for label in add_labels if label not in node_labels or
                                  node_labels[label] != add_labels[label]}
                if missing_labels:
                    print("Adding labels %s to %s" % (missing_labels, node_name))
                    body = {"metadata": {"labels": missing_labels}}
                    v1.patch_node(node_name, body)
