#!/usr/bin/env python3

import argparse
import json
import logging
import os
import subprocess
import tempfile
import threading
import yaml

def parse_config(path):
    with open(path) as cp:
        conf = yaml.safe_load(cp)

    required_fields = { 'users', 'cert', 'key' }
    missing_fields = required_fields - set(conf.keys())

    if missing_fields:
        raise RuntimeError('Missed params in config file: {}'.format(missing_fields))

    user_req_fields = { 'port', 'password', 'method' }
    for user in conf['users']:
        missing_fields = user_req_fields - set(user.keys())
        if missing_fields:
            raise RuntimeError('Missed params in users section of config file: {}'.format(missing_fields)) 
    return conf


def gen_sslh_conf(path):
    protos = []
    for conf in config.get('users', []) + config.get('services', []):
        if 'tls' not in conf:
            continue

        protos.append(f'''
    {{
        name: "tls";
        host: "{ conf['host'] if 'host' in conf else '127.0.0.1' }";
        port: "{ conf['port'] }";
        sni_hostnames: [ "{ conf['sni'] }" ];
    }}''')

    res = '''
protocols: (
  {}
);'''.format(','.join(protos))

    with open(path, 'w+') as cp:
        cp.write(res)

def gen_haproxy_conf(path):
    res = ''
    back_names = []
    for conf in config.get('users', []) + config.get('services', []):
        back_names.append(conf['sni'])

        res += f'''
backend { conf['sni'] }
    mode tcp
    option tcp-check
    server name { conf['host'] if 'host' in conf else '127.0.0.1'}:{conf['port']} check
'''

    res += '''

frontend tls_in
    bind *:443
    mode tcp
    tcp-request inspect-delay 5s
    tcp-request content accept if { req_ssl_hello_type 1 }
'''
    for name in back_names:
        if name == 'default':
            continue

        res += f'''
    use_backend { name } if {{ req.ssl_sni -i { name } }}'''
        
    if 'default' in back_names:
        res+= '''
    default_backend default
'''
    with open(path, 'w+') as cp:
        cp.write(res)

def gen_ss_conf(params, path):
    user_conf = {
            "server": params['host'] if 'host' in params else '127.0.0.1',
            "server_port": params['port'],
            "password": params['password'],
            "method": params['method'],
            "mode": "tcp_only"
    }
    if 'tls' in params:
        global config
        user_conf.update({
            "plugin": "v2ray-plugin",
            "plugin_opts": f"server;tls;host={ params['sni'] };cert={ config['cert'] };key={ config['key'] }"
        })

    with open(path, 'w+') as cp:
        json.dump(user_conf, cp, indent=2)


def run_ss(conf_path):
    global config

    cmd = 'ss-server -c {}'.format(conf_path)

    logging.info('Starting new ss-server: {}'.format(cmd))
    subprocess.run(cmd.split())

if __name__ == "__main__":
    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument("--config", "-c", type=str, required=True, help="Config path")
    cmdparser.add_argument("--sslh", "-S", type=str, dest="sslh_conf", help="Path to SSLH config")
    cmdparser.add_argument("--haproxy", "-H", type=str, dest="haproxy_conf", help="Path to HaProxy config")
    cmdparser.add_argument("--debug", "-D", action="store_true", help="debug")
    cmdargs = cmdparser.parse_args()

    logging.basicConfig(level=logging.INFO if not cmdargs.debug else logging.DEBUG, format="%(asctime)s %(name)s - %(levelname)s - %(message)s")

    config = parse_config(cmdargs.config)

    tmp_dir = tempfile.mkdtemp(prefix="ss-runner-")
    logging.info('Creating temporary directory {}'.format(tmp_dir))

    if cmdargs.sslh_conf:
        gen_sslh_conf(cmdargs.sslh_conf)
    elif cmdargs.haproxy_conf:
        gen_haproxy_conf(cmdargs.haproxy_conf)

    threads = []
    for user_conf in config['users']:
        conf_path = os.path.join(tmp_dir, '{}.conf'.format(user_conf['port']))
        gen_ss_conf(user_conf, conf_path)
        threads.append(threading.Thread(name="ss_{}".format(user_conf['port']), target=run_ss, args=(conf_path,)))

    [ thr.start() for thr in threads ]
