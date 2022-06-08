# ss-runner
Hello. ss-runner is an small utility which allows you to run multiple instances of [shadowsocks-libev](https://github.com/shadowsocks/shadowsocks-libev) behind [sslh](https://github.com/yrutschle/sslh). It can help you to fix two problems:
1. Your ShadowSocks connections will look like HTTPS connections.
2. You can create several accounts and use it with one endpoint with different SNI-hostnames.

## How it works
Script will generate configuration files for ss-server and sslh, put it on a temporary directory, start sslh with 443 port opened to outside and start one ss-server for each user account with port, binded to localhost.

When someone will try to connect, sslh will parse SNI-hostname of client connection and forward connection to ss-server, associated with it.

## How to use
You will need [shadowsocks-libev](https://github.com/shadowsocks/shadowsocks-libev), [v2ray-plugin](https://github.com/shadowsocks/v2ray-plugin) and [sslh](https://github.com/yrutschle/sslh) in your $PATH, SSL-certificate with wildcard for your hostname(from [Let's Encrypt](https://letsencrypt.org/) for example) and root access to your server(because you will need to open 443 port).

Just rewrite example config with your configuration and run `./ss-runner.py -c ss-runner.yaml` . On a client-side you will need to use v2ray plugin with websocket mode and enabled TLS.
