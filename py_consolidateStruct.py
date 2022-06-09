"""
Script to remove 'learned' from redistribution in secondary VLANs
"""
from pathlib import Path
from pathlib import PurePath
from yaml import dump
from yaml import load
from yaml import SafeDumper
from yaml.loader import FullLoader
from ciscoconfparse import CiscoConfParse
from git import Repo
from git.exc import GitCommandError

class NoAliasDumper(SafeDumper):
    def ignore_aliases(self, data):
        return True
    def increase_indent(self, flow=False, indentless=False):
        return super(NoAliasDumper, self).increase_indent(flow, False)

def rm_listDup(evalList):
    """ Remove Duplicates From List"""
    clean_list = list(dict.fromkeys(evalList))
    return clean_list

def replaceInFile(srcFile, origin, target):
    """ Replace String Occurrences In A File """
    with open(srcFile, 'r') as f:
        yamlFileData = f.read() 
    yamlFileData = yamlFileData.replace(origin, target)
    with open(srcFile, 'w+') as f:
        f.write(yamlFileData)

def mv_yamlFiles(src_dir, dst_dir):
    """ Move YML files """
    print('Moving files from '+ str(src_dir) + ' to ' + str(dst_dir) + '...')
    for fileIn_dirFile in src_dir.iterdir():
        Path(dst_dir).mkdir(exist_ok=True)
        if PurePath(str(fileIn_dirFile)).match('*.yml'):
            fileIn_dirString = str(fileIn_dirFile)
            dev_file = fileIn_dirString.replace(str(src_dir), '')
            dev_filePath = dst_dir / dev_file[1:]
            fileIn_dirFile.replace(dev_filePath)

def cloneRepo(repoBranch, repo_dst, remoteRepo='git@git.build.acmegrp.acme.com:network-automation-dev/sdn-fabric'):
    """ CLONE OR PULL SDN-FABRIC REPOSITORY """
    try:
        Repo.clone_from(remoteRepo, repo_dst, branch=repoBranch)
    except GitCommandError:
        print('WARNING! Repository is already cloned...')
        repo = Repo(repo_dst)
        print('Pulling updates instead...')
        repo.remotes.origin.pull()

def dictSimpleMerge(mainKey,runDict, yamlDict):
    """ Evaluate and merge config section"""
    if mainKey in runDict:
        for key in runDict[mainKey]:
            if key not in yamlDict[mainKey]:
                yamlDict[mainKey][key] = runDict[mainKey][key].copy()
            else:
                pass
    return yamlDict

def main():
    """Main Program"""
    #### SCRIPT VARIABLES ###
    structured_hostDir = Path('intended/structured_configs/')
    run_data_dir = Path('sdn_fabric_data/')
    isolated_all_list = []
    pwd = Path('py_consolidateStruct.py')
    repo_absDir = pwd.absolute()
    repo_rootDir = repo_absDir.parent.parent
    repo_dir = Path('sdn-fabric/')
    repo_dst = repo_rootDir / repo_dir
    dev_filesDir = Path('playbooks/intended/structured_configs')
    dev_files = repo_dst / dev_filesDir

    ### CLONE OR PULL SDN-FABRIC REPOSITORY ###
    print('Cloning sdn-fabric repository...')
    cloneRepo('master', repo_dst)
    mv_yamlFiles(dev_files, run_data_dir)
    print('*' * 100)

    ### LOAD STRUCTURED DATA ###
    print('Remove redistribute-learned From Secondary Private VLANs...')
    print('Add OSPF to BGP Route Redistribution...')
    print('Add BGP to OSPF Route Redistribution...')
    for hostname_file in structured_hostDir.iterdir():
        if PurePath(str(hostname_file)).match('*.yml'):
            with open(hostname_file) as f:
                host_dict = load(f, Loader=FullLoader)
            isolatedVlan_list = []
            if 'vlans' in host_dict:
                for vlan in host_dict['vlans']:
                    if 'private_vlan' in host_dict['vlans'][vlan]:
                        isolatedVlan_list.append(vlan)
                        isolated_all_list.append(vlan)
            if 'vrfs' in host_dict['router_bgp']:
                for bgpVrf in host_dict['router_bgp']['vrfs'].copy():
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-STATIC-TO-BGP']= {}
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-STATIC-TO-BGP']['sequence_numbers'] = {}
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-STATIC-TO-BGP']['sequence_numbers'][100] = {}
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-STATIC-TO-BGP']['sequence_numbers'][100]['type'] = 'permit'
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-CONNECTED-TO-BGP']= {}
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-CONNECTED-TO-BGP']['sequence_numbers'] = {}
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-CONNECTED-TO-BGP']['sequence_numbers'][100] = {}
                    host_dict['route_maps']['RM-' + bgpVrf.upper() + '-CONNECTED-TO-BGP']['sequence_numbers'][100]['type'] = 'permit'
                    host_dict['router_bgp']['vrfs'][bgpVrf]['redistribute_routes'] = {}
                    host_dict['router_bgp']['vrfs'][bgpVrf]['redistribute_routes']['connected'] = {}
                    host_dict['router_bgp']['vrfs'][bgpVrf]['redistribute_routes']['connected']['route_map'] = 'RM-' + bgpVrf.upper() + '-CONNECTED-TO-BGP'
                    host_dict['router_bgp']['vrfs'][bgpVrf]['redistribute_routes']['static'] = {}
                    host_dict['router_bgp']['vrfs'][bgpVrf]['redistribute_routes']['static']['route_map'] = 'RM-' + bgpVrf.upper() + '-STATIC-TO-BGP'
            for core_subIf in host_dict['ethernet_interfaces']:
                if 'eos_cli' in host_dict['ethernet_interfaces'][core_subIf] and 'ip ospf area 0.0.0.0' == host_dict['ethernet_interfaces'][core_subIf]['eos_cli']:
                    coreVrfId = host_dict['ethernet_interfaces'][core_subIf]['vrf']
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-OSPF-TO-BGP']= {}
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-OSPF-TO-BGP']['sequence_numbers'] = {}
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-OSPF-TO-BGP']['sequence_numbers'][100] = {}
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-OSPF-TO-BGP']['sequence_numbers'][100]['type'] = 'permit'
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-BGP-TO-OSPF']= {}
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-BGP-TO-OSPF']['sequence_numbers'] = {}
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-BGP-TO-OSPF']['sequence_numbers'][100] = {}
                    host_dict['route_maps']['RM-' + coreVrfId.upper() + '-BGP-TO-OSPF']['sequence_numbers'][100]['type'] = 'permit'
                    host_dict['router_bgp']['vrfs'][coreVrfId]['redistribute_routes']['ospf'] = {}
                    host_dict['router_bgp']['vrfs'][coreVrfId]['redistribute_routes']['ospf']['route_map'] = 'RM-' + host_dict['ethernet_interfaces'][core_subIf]['vrf'].upper() + '-OSPF-TO-BGP'            
                    for ospfProcess in host_dict['router_ospf']['process_ids'].copy():
                        if coreVrfId == host_dict['router_ospf']['process_ids'][ospfProcess]['vrf']:
                            host_dict['router_ospf']['process_ids'][ospfProcess]['redistribute']['bgp']['route_map'] = 'RM-' + coreVrfId.upper() + '-BGP-TO-OSPF'

    ### REMOVE REDISTRIBUTE LEARNED FROM ISOLATED VLANS IN BGP (STRUCTURED DATA) ###
            if 'vlans' in host_dict['router_bgp']:
                for isolatedVlan in isolatedVlan_list:
                    host_dict['router_bgp']['vlans'][isolatedVlan]['redistribute_routes'] = []
    ### DUMP DICT TO YAML FILE ###
            with open(str(hostname_file), 'w+') as yaml_file:
                dump(host_dict, yaml_file, default_flow_style=False, width=1000, Dumper=NoAliasDumper) 
    print('*' * 100)
    
    """ Merge Running Configs Data Structure with Required Data """
    #### GET RUNNING CONFIGURATIONS PER HOST AND TRANSFER TO AN OBJECT ###
    dh01yaml_files_list = []
    for dh01yaml_dir in structured_hostDir.iterdir():
        if PurePath(str(dh01yaml_dir)).match('*dh01*.yml'):
            dh01yaml_files_list.append(dh01yaml_dir)
    dh01running_files_list = []
    for dh01running_dir in run_data_dir.iterdir():
        if PurePath(str(dh01running_dir)).match('*dh01*.yml'):
            dh01running_files_list.append(dh01running_dir)

    for hostRun_dir, hostYaml_dir in zip(dh01running_files_list, dh01yaml_files_list):
        if PurePath(str(hostYaml_dir)).match('*.yml') and PurePath(str(hostRun_dir)).match('*.yml'):
            print('Evaluating: ' + str(hostRun_dir).replace(str(run_data_dir),'').upper())
            with open(hostYaml_dir) as f:
                hostYamlDict = load(f, Loader=FullLoader)
            with open(hostRun_dir) as f:
                hostRunDict = load(f, Loader=FullLoader)

            #### EVALUATE LOOPBACK IPS ###
            print('Merging Loopback IPs...')
            trans_loopIp = hostYamlDict['loopback_interfaces']['Loopback0']['ip_address'].replace('/32','')
            loopIp = hostRunDict['loopback_interfaces']['Loopback0']['ip_address'].replace('/32','')
            replaceInFile(hostYaml_dir, trans_loopIp,loopIp)
            with open(hostYaml_dir) as f:
                hostYamlDict = load(f, Loader=FullLoader)
            for loopbackId in hostRunDict['loopback_interfaces']:
                hostYamlDict['loopback_interfaces'][loopbackId] = hostRunDict['loopback_interfaces'][loopbackId].copy()
        
            ### EVALUATE MLAG CONFIGURATION ###
            print('Merge MLAG Configuration')
            if 'mlag_configuration' in hostRunDict:
                hostYamlDict['mlag_configuration'] = hostRunDict['mlag_configuration'].copy()

            #### EVALUATE ROUTER BGP PEER GROUPS ### 
            print('Merging BGP...')
            dictSimpleMerge('peer_groups', hostRunDict['router_bgp'], hostYamlDict['router_bgp'])
    
            ### EVALUATE IPV4 ADDRESS FAMILY ###
            dictSimpleMerge('peer_groups', hostRunDict['router_bgp']['address_family_ipv4'], hostYamlDict['router_bgp']['address_family_ipv4'])
    
            ### EVALUATE NEIGHBORSHIPS ###
            hostYamlDict['router_bgp']['neighbors'] = hostRunDict['router_bgp']['neighbors'].copy()
    
            ### EVALUATE L2 MAC VRFS ###
            if 'vlans' in hostRunDict['router_bgp']:
                dictSimpleMerge('vlans', hostRunDict['router_bgp'], hostYamlDict['router_bgp'])
            else:
                pass
            
            ### EVALUATE L3 IP VRFS ###
            if 'vrfs' in hostRunDict['router_bgp']:
                dictSimpleMerge('vrfs', hostRunDict['router_bgp'], hostYamlDict['router_bgp'])
            else:
                pass    

            ### EVALUATE P2P LINKS ###
            print('Merging Ethernet Interfaces...')
            for ethIf in hostRunDict['ethernet_interfaces']:
                if 'description' in hostRunDict['ethernet_interfaces'][ethIf] and 'P2P_LINK_TO_SWEX-D' in hostRunDict['ethernet_interfaces'][ethIf]['description']:
                    hostYamlDict['ethernet_interfaces'][ethIf] = hostRunDict['ethernet_interfaces'][ethIf].copy()
                elif 'description' in hostRunDict['ethernet_interfaces'][ethIf] and 'MLAG_PEER_' in hostRunDict['ethernet_interfaces'][ethIf]['description']:
                    hostYamlDict['ethernet_interfaces'][ethIf] = hostRunDict['ethernet_interfaces'][ethIf].copy()
                elif ethIf not in hostYamlDict['ethernet_interfaces']:
                    hostYamlDict['ethernet_interfaces'][ethIf] = hostRunDict['ethernet_interfaces'][ethIf].copy()
            
            ### EVALUATE VXLAN ###
            if 'vxlan_tunnel_interface' in hostRunDict:
                print('Merging VXLAN...')
                dictSimpleMerge('vlans', hostRunDict['vxlan_tunnel_interface']['Vxlan1']['vxlan_vni_mappings'], hostYamlDict['vxlan_tunnel_interface']['Vxlan1']['vxlan_vni_mappings'])
                dictSimpleMerge('vrfs', hostRunDict['vxlan_tunnel_interface']['Vxlan1']['vxlan_vni_mappings'], hostYamlDict['vxlan_tunnel_interface']['Vxlan1']['vxlan_vni_mappings'])
            else:
                pass
            
            ### EVALUATE PORT CHANNELS ###
            if 'port_channel_interfaces' in hostRunDict:
                print('Merging Port Channel Interfaces...')
                hostYamlDict['port_channel_interfaces'] = hostRunDict['port_channel_interfaces'].copy()
            
            ### EVALUATE VLANS ###
            print('Merging VLANs...')
            dictSimpleMerge('vlans',hostRunDict, hostYamlDict)
            
            ### EVALUATE VRFS ###
            print('Merging VRFs...')
            dictSimpleMerge('vrfs',hostRunDict, hostYamlDict)
            
            ### EVALUATE SVIS ###
            print('Merging SVIs...')
            if 'vlan_interfaces' in hostRunDict:
                dictSimpleMerge('vlan_interfaces', hostRunDict, hostYamlDict)
                dictSimpleMerge('Vlan4093', hostRunDict['vlan_interfaces']['Vlan4093'], hostYamlDict['vlan_interfaces']['Vlan4093'])
                dictSimpleMerge('Vlan4094', hostRunDict['vlan_interfaces']['Vlan4094'], hostYamlDict['vlan_interfaces']['Vlan4094'])
            
            ### EVALUATE ROUTE-MAPS ###
            print('Merging route-maps...')
            if 'route_maps' in hostRunDict:
                dictSimpleMerge('route_maps', hostRunDict, hostYamlDict)
            
            ### EVALUATE PREFIX-LISTS ###
            print('Merging prefix-lists...')
            if 'prefix_lists' in hostRunDict:
                dictSimpleMerge('prefix_lists', hostRunDict, hostYamlDict)

            ### EVALUATE EXTENDED ACCESS-LISTS ###
            print('Merging extended access-lists...')
            if 'access_lists' in hostRunDict:
                dictSimpleMerge('access_lists', hostRunDict, hostYamlDict)

            ### EVALUATE STANDARDACCESS-LISTS ###
            print('Merging standard access-lists...')
            if 'standard_access_lists' in hostRunDict:
                dictSimpleMerge('standard_access_lists', hostRunDict, hostYamlDict)

            ### REMOVE BFD ###
            if 'router_bfd' in hostYamlDict.copy():
                hostYamlDict.pop('router_bfd', None)
    
            ### REMOVE TENANT & TAGS ###
            if 'vlans' in hostYamlDict['router_bgp'].copy():
                for bgpVlan in hostYamlDict['router_bgp']['vlans'].copy():
                    hostYamlDict['router_bgp']['vlans'][bgpVlan].pop('tenant', None)
            if 'vlan_interfaces' in hostYamlDict.copy():
                for svi in hostYamlDict['vlan_interfaces'].copy():
                    hostYamlDict['vlan_interfaces'][svi].pop('tenant', None)
                    hostYamlDict['vlan_interfaces'][svi].pop('tags', None)
            if 'vlans' in hostYamlDict.copy():
                for vlanId in hostYamlDict['vlans'].copy():
                    hostYamlDict['vlans'][vlanId].pop('tenant', None)
            if 'vrfs' in hostYamlDict.copy():
                for vrf in hostYamlDict['vrfs'].copy():
                    hostYamlDict['vrfs'][vrf].pop('tenant', None)
            
            ### DUMP YAML DICTS TO FILES ###
            print('Updating Files...')
            with open(hostYaml_dir, 'w+') as yaml_file:
                dump(hostYamlDict, yaml_file, default_flow_style=False, width=1000, Dumper=NoAliasDumper) 
            print('*' * 100)
       
    ### PUSH FILES TO BRANCH ### 
    print('Checking out branch...')
    repo = Repo(repo_dst)
    dev_commitFile_list = []
    print(repo.git.checkout('user_devel3'))
    ### COPY YAML MERGED FILES INTO BRANCH ###
    print('Copying Merged Files Into Repository...')  
    for dev_structPath in structured_hostDir.iterdir():
        if PurePath(str(dev_structPath)).match('*.yml'):
            dev_structFile = str(dev_structPath).replace(str(structured_hostDir),'')[1:]
            dev_commitFile = dev_filesDir / dev_structFile 
            dev_commitFile_list.append(str(dev_commitFile))
            repo_dstStructFile = dev_files / dev_structFile
            repo_dstStructFile.write_bytes(dev_structPath.read_bytes()) 
    ### CONT. PUSH FILES TO BRANCH ### 
    print('Adding Files to Repository...')
    repo.index.add(dev_commitFile_list)
    print('Committing to Repository...')
    print(repo.index.commit('Add Structured Data Files To Repo.'))
    print('Pushing changes..')
    print(repo.remotes.origin.push())

if __name__ == '__main__':
    main()
