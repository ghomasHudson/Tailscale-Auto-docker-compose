import yaml
import os
import json
import copy
import watchdog.events
import argparse


def transform_config(args):
    print("Transforming config...")
    docker_config = yaml.safe_load(args.input_config_file)
    docker_config_new = copy.deepcopy(docker_config)

    tailscale_base_path = os.path.join(os.path.dirname(args.input_config_file.name), '.tailscale')
    if not os.path.exists(tailscale_base_path):
        os.makedirs(os.path.join(tailscale_base_path, 'states'))
        os.makedirs(os.path.join(tailscale_base_path, 'serve_configs'))

    for service in docker_config['services']:
        labels = docker_config['services'][service].get('labels', {})

        # Get tailscale.X labels
        tailscale_config = {}
        for key in labels:
            if key.startswith('tailscale.') and "=" in key:
                key, value = key.split('=', 1)
                key = key.split('tailscale.', 1)[1]
                tailscale_config[key] = value

        if len(tailscale_config) == 0:
            continue

        if args.ts_authkey:
            environment = [ 'TS_AUTHKEY=' + args.ts_authkey,
            ]
        elif args.ts_oauth_client_secret:
            environment = [
                'TS_AUTHKEY=' + args.ts_oauth_client_secret + "?ephemeral=false",
                'TS_EXTRA_ARGS=--advertise-tags=tag:docker'
            ]

        docker_config_new['services'][service]['network_mode'] = 'service:ts-' + service
        docker_config_new['services'][service]['depends_on'] = ['ts-' + service]
        docker_config_new['services']["ts-" + service] = {
            'image': 'tailscale/tailscale:latest',
            'container_name': 'ts-' + service,
            'hostname': service,
            'environment': [
                "TS_STATE_DIR=/var/lib/tailscale",
                'TS_SERVE_CONFIG=/config/' + service + ".json",
            ] + environment,
            'volumes': [
                os.path.join(tailscale_base_path, 'states', service) + ':/var/lib/tailscale',
                os.path.join(tailscale_base_path, 'serve_configs') + ':/config',
                "/dev/net/tun:/dev/net/tun"
            ],
            "cap_add": ["net_admin", "sys_module"],
            "restart": "unless-stopped",
        }


        allowFunnel = tailscale_config.get('allowFunnel', "false")
        allowFunnel = True if allowFunnel.lower() == 'true' else False

        # Make json config
        with open(os.path.join(tailscale_base_path, 'serve_configs', service + '.json'), 'w') as f:

            f.write(json.dumps({
                    "TCP": {"443": {"HTTPS": True}},
                    "Web": {"${TS_CERT_DOMAIN}:443": {
                        "Handlers": {
                            "/" : { "Proxy": "http://127.0.0.1:" + tailscale_config.get('port', '80') }
                        }
                    }},
                    "AllowFunnel": { "${TS_CERT_DOMAIN}:443": allowFunnel }
            }, indent=2))

    args.output_config_file.write("""# This file is generated by make_tailscale.py
#
# Do not edit this file directly. Edit compose.main.yaml instead.
#
# To apply changes, run:
#   make_tailscale.py
#
""" +
    yaml.dump(docker_config_new, indent=2))
    print(args.output_config_file.name, " updated")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_config_file', type=argparse.FileType('r'), default='compose.main.yaml')
    parser.add_argument('--output_config_file', type=argparse.FileType('w'), default='compose.yaml')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--ts_authkey', type=str)
    group.add_argument('--ts_oauth_client_secret', type=str)

    args = parser.parse_args()

    # Run the transformation when the input_config_file changes
    class EventHandler(watchdog.events.FileSystemEventHandler):
        def on_modified(self, event):
            if os.path.exists(event.src_path):
                if os.path.samefile(event.src_path, args.input_config_file.name):
                    transform_config(args)


    transform_config(args)

    import watchdog.observers
    observer = watchdog.observers.Observer()
    observer.schedule(EventHandler(), path=os.path.dirname(args.input_config_file.name))
    print("Watching for changes to", args.input_config_file.name)
    observer.start()
    observer.join()
