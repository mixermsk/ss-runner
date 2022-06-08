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
    cp = open(path)
    conf = yaml.load(cp)

    required_fields = {'users', 'cert', 'key'}
    missing_fields = required_fields - set(conf.keys())

    if missing_fields:
        raise RuntimeError('Missed params in config file: {}'.format(missing_fields))

    user_req_fields = {'port', 'password', 'method'}
    for user in conf['users']:
        if 'host' not in user:
            user['host'] = 'localhost'

        missing_fields = user_req_fields - set(user.keys())
        if missing_fields:
            raise RuntimeError('Missed params in users section of config file: {}'.format(missing_fields))

    return conf


def gen_sslh_conf(path):
    protos = []
    for user_conf in config['users'] + config.get('sslh-protos', []):
        if 'tls' not in user_conf:
            continue

        protos.append('''
    {{
        name: "tls";
        host: "{}";
        port: "{}";
        sni_hostnames: [ "{}" ];
    }}'''.format(user_conf['host'], user_conf['port'], user_conf['tls-host']))

    conf = '''
protocols: (
  {}
);'''.format(','.join(protos))
    with open(path, 'w+') as cp:
        cp.write(conf)


def gen_ss_conf(params, path):
    user_conf = {
            "server": params['host'],
            "server_port": params['port'],
            "password": params['password'],
            "method": params['method'],
            "mode": "tcp_only"
    }
    if 'tls' in params:
        global config
        user_conf.update({
            "plugin": "v2ray-plugin",
            "plugin_opts": "server;tls;host={};cert={};key={}".format(params['tls-host'], config['cert'], config['key'])
        })

    with open(path, 'w+') as cp:
        json.dump(user_conf, cp, indent=2)


def run_ss(conf_path):
    global config

    cmd = 'ss-server -c {}'.format(conf_path)

    logging.info('Starting new ss-server: {}'.format(cmd))
    subprocess.check_output(cmd.split())


def run_sslh(conf):
    cmd = 'sudo sslh -f --user sslh --listen 0.0.0.0:443 -F {}'.format(conf)
    logging.info('Starting sslh: {}'.format(cmd))
    subprocess.check_output(cmd.split())


if __name__ == "__main__":
    cmdparser = argparse.ArgumentParser()
    cmdparser.add_argument("--config", "-c", type=str, required=True, help="Config path")
    cmdparser.add_argument("--debug", "-D", action="store_true", help="debug")
    cmdargs = cmdparser.parse_args()

    logging.basicConfig(level=logging.INFO if not cmdargs.debug else logging.DEBUG, format="%(asctime)s %(name)s - %(levelname)s - %(message)s")

    config = parse_config(cmdargs.config)

    tmp_dir = tempfile.mkdtemp(prefix="ss-runner-")
    logging.info('Creating temporary directory {}'.format(tmp_dir))

    sslh_conf = os.path.join(tmp_dir, 'sslh.conf')
    gen_sslh_conf(sslh_conf)

    threads = []
    threads.append(threading.Thread(name="sslh", target=run_sslh, args=(sslh_conf,)))

    for user_conf in config['users']:
        conf_path = os.path.join(tmp_dir, '{}.conf'.format(user_conf['port']))
        gen_ss_conf(user_conf, conf_path)
        threads.append(threading.Thread(name="ss_{}".format(user_conf['port']), target=run_ss, args=(conf_path,)))

    [thr.start() for thr in threads]
