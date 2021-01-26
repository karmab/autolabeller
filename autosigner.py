from base64 import b64decode
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from OpenSSL.crypto import FILETYPE_PEM, load_certificate_request
import yaml
from kubernetes import client, config, watch
import os
import re
import threading


def watch_configmaps():
    while True:
        stream = watch.Watch().stream(v1.list_namespaced_config_map, namespace, timeout_seconds=10)
        for event in stream:
            obj = event["object"]
            obj_dict = obj.to_dict()
            current_config_map_name = obj_dict['metadata']['name']
            if current_config_map_name == config_map_name and event["type"] == 'MODIFIED':
                print("Exiting as configmap was changed")
                os._exit(1)


def watch_csrs():
    while True:
        stream = watch.Watch().stream(certs_api.list_certificate_signing_request, timeout_seconds=10)
        for event in stream:
            obj = event["object"]
            obj_dict = obj.to_dict()
            csr_name = obj_dict['metadata']['name']
            request = obj_dict['spec']['request']
            usages = obj_dict['spec'].get('usages', [])
            username = obj_dict['spec']['username']
            groups = obj_dict['spec']['groups']
            if 'client auth' in usages:
                if username != 'system:serviceaccount:openshift-machine-config-operator:node-bootstrapper':
                    print("Incorrect username in csr %s. Ignoring" % csr_name)
                    continue
                if sorted(groups) != ['system:authenticated', 'system:serviceaccounts',
                                      'system:serviceaccounts:openshift-machine-config-operator']:
                    print("Incorrect group in csr %s. Ignoring" % csr_name)
                    continue
            elif 'server auth' in usages:
                if sorted(groups) != ['system:authenticated', 'system:nodes']:
                    print("Incorrect group in csr %s. Ignoring" % csr_name)
                    continue
            else:
                continue
            cert_type = 'client' if 'client auth' in usages else 'server'
            status = obj_dict['status']
            if status['conditions'] is None:
                csr_pem = b64decode(request)
                csr = load_certificate_request(FILETYPE_PEM, csr_pem)
                cert_name = str(csr.get_subject())
                common_names = [e[1].decode() for e in csr.get_subject().get_components() if e[0].decode() == 'CN']
                if not common_names:
                        print("Invalid common name in csr %s. Ignoring" % csr_name)
                        continue
                else:
                    common_name = common_names[0]
                if 'server auth' in usages:
                    if username != common_name:
                        print("Incorrect username in csr %s. Ignoring" % csr_name)
                        continue
                    for extension in csr.get_extensions():
                        clean_extension = str(extension)
                        if clean_extension.startswith('DNS') and 'IP Address:' in clean_extension:
                            clean_extension_split = clean_extension.split(',')
                            dns = clean_extension_split[0].replace('DNS:', '')
                            if 'system:node:%s' % dns != common_name:
                                print("Incorrect DNS name in csr %s. Ignoring" % csr_name)
                                continue
                            if allowed_networks:
                                allowed = False
                                ip = clean_extension_split[1].replace('IP Address:', '').strip()
                                for cidr in allowed_networks:
                                    if ip_address(ip) in ip_network(cidr):
                                        allowed = True
                                        break
                                if not allowed:
                                    print("Invalid Ip %s from csr %s. Ignoring" % (ip, csr_name))
                                    continue
                for rule in name_rules:
                    if re.match(rule, cert_name):
                        print("Signing %s cert %s" % (cert_type, csr_name))
                        body = certs_api.read_certificate_signing_request_status(csr_name)
                        now = datetime.now(timezone.utc).astimezone()
                        message = "Signed by Karmab autosigner"
                        reason = "Matching autosigner rules"
                        approval_condition = client.V1beta1CertificateSigningRequestCondition(last_update_time=now,
                                                                                              message=message,
                                                                                              reason=reason,
                                                                                              type='Approved')
                        body.status.conditions = [approval_condition]
                        certs_api.replace_certificate_signing_request_approval(csr_name, body)
                        break
                continue


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
    allowed_networks = []
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
        if 'allowed_networks' in data and isinstance(data['allowed_networks'], list):
            allowed_networks = data['allowed_networks']
            for network in allowed_networks:
                try:
                    ip_network(network)
                except:
                    print("Incorrect entry %s in allowed_network of configmap. Leaving" % network)
                    os._exit(1)
            print("Only allowing networks from %s" % allowed_networks)
            name_rules.append(newname)
    if not allowed_networks:
        print("No specific allowed_networks defined. No check on ips will be made" % allowed_networks)
    print("Starting main signing loop...")
    threading.Thread(target=watch_csrs).start()
    threading.Thread(target=watch_configmaps).start()
