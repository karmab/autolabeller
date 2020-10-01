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
        namespace = os.open(k8sfile).read() if os.path.exists(k8sfile) else os.environ.get('NAMESPACE', 'default')
        config_map_name = os.environ.get('CONFIG_MAP', 'labelrules')
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
        newname, newlabels, newmatchlabels = data.get('name'), data.get('labels'), data.get('matchlabels')
        if newlabels is None:
            print("No valid labels found in rule %s.Ignoring" % entry)
            continue
        elif newname is not None:
            print("Handling name rule %s with labels %s" % (newname, newlabels))
            name_rules[newname] = newlabels
        elif newmatchlabels is not None:
            print("Handling matchlabels rule %s with labels %s" % (newmatchlabels, newlabels))
            newmatchlabelsstring = ','.join(newmatchlabels)
            label_rules[newmatchlabelsstring] = newlabels
    print("Starting main loop...")
    while True:
        stream = watch.Watch().stream(v1.list_node, timeout_seconds=10)
        for event in stream:
            obj = event["object"]
            obj_dict = obj.to_dict()
            node_name = obj_dict['metadata']['name']
            node_labels = obj_dict['metadata']['labels']
            missing_labels = []
            for name in name_rules:
                if re.match(name, node_name):
                    labels = name_rules[name]
                    missing_labels.extend([label for label in labels if label not in node_labels])
            for matchlabels in label_rules:
                if not [label for label in matchlabels.split(',') if label not in node_labels]:
                    labels = label_rules[matchlabels]
                    missing_labels.extend([label for label in labels if label not in node_labels])
            if missing_labels:
                print("Adding labels %s to %s" % (','.join(missing_labels), node_name))
                new_labels = {k: '' for k in missing_labels}
                node_labels.update(new_labels)
                obj.metadata.labels = node_labels
                v1.replace_node(node_name, obj)
