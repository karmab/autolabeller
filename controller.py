import yaml
from kubernetes import client, config, watch
import os
import re

NAMESPACE, CONFIG_MAP_NAME = 'default', 'labelrules'


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
        config_map = v1.read_namespaced_config_map(namespace=NAMESPACE, name=CONFIG_MAP_NAME)
    except Exception as e:
        if e.status == 404:
            print("Missing configmap %s in namespace %s" % (CONFIG_MAP_NAME, NAMESPACE))
        else:
            print(e)
        os._exit(0)
    rules = {}
    config_map_data = config_map.to_dict().get('data', {})
    if not config_map_data:
        print("No rules defined, using dummy worker one")
        config_map_data = {'rules1.properties': 'name: .*worker.*\nlabels:\n- node-role.kubernetes.io/worker=\n'}
    else:
        for entry in config_map_data:
            try:
                data = yaml.safe_load(config_map_data[entry])
            except yaml.scanner.ScannerError as err:
                print("Incorrect configmap. Leaving")
                os._exit(1)
            rules[data['rule']] = data['labels']
    # resource_version = ''
    print("Starting main loop...")
    while True:
        stream = watch.Watch().stream(v1.list_node, timeout_seconds=10)
        for event in stream:
            obj = event["object"]
            operation = event['type']
            obj_dict = obj.to_dict()
            node_name = obj_dict['metadata']['name']
            node_labels = obj_dict['metadata']['labels']
            for rule in rules:
                if re.match(rule, node_name):
                    labels = rules[rule]
                    missing_labels = [label for label in labels if label not in node_labels]
                    if missing_labels:
                        print("Adding labels %s to %s" % (','.join(missing_labels), node_name))
                        new_labels = {k: '' for k in missing_labels}
                        node_labels.update(new_labels)
                        obj.metadata.labels = node_labels
                        v1.replace_node(node_name, obj)
                        continue
