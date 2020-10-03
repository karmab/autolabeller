from base64 import b64decode
from datetime import datetime, timezone
from OpenSSL.crypto import FILETYPE_PEM, load_certificate_request
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
    certs_api = client.CertificatesV1beta1Api()
    try:
        k8sfile = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
        namespace = open(k8sfile, 'r').read() if os.path.exists(k8sfile) else os.environ.get('NAMESPACE', 'default')
        config_map_name = os.environ.get('CONFIG_MAP', 'autorules')
        config_map = v1.read_namespaced_config_map(namespace=namespace, name=config_map_name)
        config_map_data = config_map.to_dict().get('data', {})
    except Exception as e:
        if e.status == 404:
            print("Missing configmap %s in namespace %s" % (config_map_name, namespace))
            config_map_data = {}
        else:
            print(e)
            os._exit(0)
    name_rules = []
    if not config_map_data:
        print("No rules defined, using dummy worker one")
        config_map_data = {'rules1.properties': 'name: .*worker.*\n'}
    for entry in config_map_data:
        try:
            data = yaml.safe_load(config_map_data[entry])
        except yaml.scanner.ScannerError as err:
            print("Incorrect configmap. Leaving")
            os._exit(1)
        if 'name' in data:
            newname = data['name']
            print("Handling name rule %s " % newname)
            name_rules.append(newname)
    print("Starting main loop...")
    while True:
        stream = watch.Watch().stream(certs_api.list_certificate_signing_request, timeout_seconds=10)
        for event in stream:
            obj = event["object"]
            operation = event['type']
            obj_dict = obj.to_dict()
            csr_name = obj_dict['metadata']['name']
            request = obj_dict['spec']['request']
            status = obj_dict['status']
            if status['conditions'] is None:
                csr_pem = b64decode(request)
                csr = load_certificate_request(FILETYPE_PEM, csr_pem)
                cert_name = str(csr.get_subject())
                for rule in name_rules:
                    if re.match(rule, cert_name):
                        print("Signing cert %s" % csr_name)
                        body = certs_api.read_certificate_signing_request_status(csr_name)
                        now = datetime.now(timezone.utc).astimezone()
                        message = "Signed by Karim"
                        reason = "Matching rules"
                        approval_condition = client.V1beta1CertificateSigningRequestCondition(last_update_time=now,
                                                                                              message=message,
                                                                                              reason=reason,
                                                                                              type='Approved')
                        body.status.conditions = [approval_condition]
                        certs_api.replace_certificate_signing_request_approval(csr_name, body)
                        break
                continue
