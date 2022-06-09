import getpass
from pathlib import Path
import json
from nornir import InitNornir
from nornir.plugins.tasks.networking import napalm_get
from nornir.core.filter import F
from nornir.core.inventory import Groups
from nornir.plugins.tasks.networking import netmiko_send_command
from nornir.plugins.tasks.files import write_file
from yaml import dump

def create_defaults(hosts_data):
    """Creates the inventory file"""
    data_folder = Path("config/")
    path_file = data_folder / "defaults.yml"
    with open(path_file, "w") as open_file:
        hosts_file = open_file.write(hosts_data)
    return hosts_file

def get_napalm_data(get_napalm_task, platform):
    """Retrieve device running configuration and create a file """
    json_data_dir = Path(platform + '_json_conf/')
    run_data_dir = Path(platform + '_conf/')
    #eosRun_data_dir = Path("eos_conf/")
    hostname = get_napalm_task.host.hostname
    no_domain_hostname = hostname.replace('.acme.com', '')
    host_dir = json_data_dir / no_domain_hostname
    Path(json_data_dir).mkdir(exist_ok=True)
    Path(run_data_dir).mkdir(exist_ok=True)
    Path(host_dir).mkdir(exist_ok=True)
    napalm_getters = ['config']
    for napalm_getter in napalm_getters:
        path_file_napalm = host_dir / napalm_getter
        path_file_run = run_data_dir / no_domain_hostname
        napalm_run = get_napalm_task.run(task=napalm_get, getters=[napalm_getter])
        if napalm_getter != 'config':
            napalm_run_json = json.dumps(napalm_run.result, indent=2)
            get_napalm_task.run(task=write_file, content=str(napalm_run_json),
                                filename="" + str(path_file_napalm))
        else:
            print(hostname  + ': Retrieving Running configuration...' + str(path_file_run))
            get_napalm_task.run(task=write_file, content=napalm_run.result['config']['running'],
                                filename="" + str(path_file_run))

def get_intStatus_data(get_nw_task, platform):
    """Get Interface Status Output and Write File"""
    command_var = 'show interface status'
    json_data_dir = Path(platform + '_json_data/')
    hostname = get_nw_task.host.hostname
    Path(json_data_dir).mkdir(exist_ok=True)
    hostname_clean = hostname.replace(".acme.com", "")
    hostname_json = hostname_clean + ".json"
    path_file = json_data_dir / hostname_json
    port_count_data = get_nw_task.run(
        task=netmiko_send_command,
        command_string=command_var,
        use_textfsm=True,
    )
    port_count_json = json.dumps(port_count_data.result, indent=2)
    str_data_json = str(port_count_json)
    if str_data_json != '""':
        print(
            hostname + ": Writing retrieved data into JSON..." + str(path_file)
        )
        get_nw_task.run(
            task=write_file,
            content=str(port_count_json),
            filename="" + str(path_file),
        )


def main():
    """Main Program"""
    """ Nornir setup & Initialization"""
    # Nornir Variables  
    config_path = Path("config/")
    defaults_file = "defaults.yml"
    defaults_path = config_path / defaults_file
    username = input("Username: ")
    password = getpass.getpass(prompt="Password: ", stream=None)
    defaults_dict = {"username": username, "password": password}
    defaults_path = config_path / defaults_file
  
    # Create defaults for user id
    defaults_yaml = dump(defaults_dict, default_flow_style=False)
    def_yaml_init = "---\n\n" + defaults_yaml
    create_defaults(str(def_yaml_init))

    # Initialize Nornir
    print("Connecting to devices...")
    nr = InitNornir(config_file="config/config.yml")
    nxos_dev = nr.filter(F(groups__contains='nxos_devices'))
    eos_dev = nr.filter(F(groups__contains='eos_devices'))
    nxos_dev.run(name="Creating Configs Archives", task=get_napalm_data, platform='nxos')
    eos_dev.run(name="Creating Configs Archives", task=get_napalm_data, platform='eos')
    nxos_dev.run(name="Retrieving Data", task=get_intStatus_data, platform='nxos')
    # Delete Credentials File
    Path.unlink(defaults_path)
    print("End of Script...")

if __name__ == '__main__':
    main()