"""
Script to transform config files to YAML for IaC purposes
"""
from pathlib import Path
from pathlib import PurePath
import re
import sys
import json
import csv
from yaml import dump
from yaml import load
from yaml import SafeDumper
from ciscoconfparse import CiscoConfParse
from yaml.loader import FullLoader

class NoAliasDumper(SafeDumper):
    def ignore_aliases(self, data):
        return True
    def increase_indent(self, flow=False, indentless=False):
        return super(NoAliasDumper, self).increase_indent(flow, False)

def rm_listDup(evalList):
    clean_list = list(dict.fromkeys(evalList))
    return clean_list

def read_csv_subIfs(file):
    with open(file) as csv_file:
        csv_data = csv.reader(csv_file, delimiter=';')  
        next(csv_data)
        csv_data_list = []
        for row in csv_data:
            row_dict = {}
            ethip1_string = row[2]
            ethip2_string = row[3]
            ethip1 = ethip1_string.strip('][').split(', ')
            ethip2 = ethip2_string.strip('][').split(', ')
            row_dict['vrf'] = row[0]
            row_dict['vlanId'] = row[1]
            row_dict['ethip1'] = ethip1
            row_dict['ethip2'] = ethip2
            csv_data_list.append(row_dict) 
        return csv_data_list

def vrf_vnis():
    data_dir = Path('data/')
    vrfs_file = data_dir / 'dc_vrfs.csv'
    with open(vrfs_file) as vrf_file:
        csv_vrfs = csv.reader(vrf_file, delimiter=';')  
        next(csv_vrfs)
        csv_vrfs_list = []
        for row in csv_vrfs:
            row_dict = {}
            row_dict['dc'] = row[0]
            row_dict['vrf'] = row[1]
            row_dict['vrf_vni'] = row[2]
            csv_vrfs_list.append(row_dict) 
    return csv_vrfs_list

def yaml_toFile(host, yaml_input, yamlDir='yaml_data/'):
    """Python Dict into YAML format and dumps it in a file"""
    stage_dev_file = host + '.yml'
    yaml_rootDir = Path(yamlDir)
    Path(yaml_rootDir).mkdir(exist_ok=True)
    yaml_file_path = yaml_rootDir / stage_dev_file
    with open(str(yaml_file_path), 'a+') as yaml_file:
        dump(yaml_input, yaml_file, default_flow_style=False, width=1000, Dumper=NoAliasDumper)       

def del_yamlFiles(yaml_dir):
    try:
        for hostname_file in yaml_dir.iterdir():
            try:
                Path.unlink(hostname_file)
            except Exception as e:
                print(e)
    except IOError as e:
        print(e)

def mv_yamlFiles(src_dir, dst_dir):
    for avd_dirFile in src_dir.iterdir():
        if PurePath(str(avd_dirFile)).match('*_*.yml'):
            Path(dst_dir).mkdir(exist_ok=True)
            avd_dirString = str(avd_dirFile)
            avd_file = avd_dirString.replace(str(src_dir), '')
            avd_filePath = dst_dir / avd_file[1:]
            avd_dirFile.replace(avd_filePath)

def load_yamlFile(filename):
    with open(filename) as f:
        dict_result = load(f, Loader=FullLoader )
    return dict_result

def replace_ifName():
    print('Replacing Port Names on json data...')
    json_rootDir = Path('nxos_json_data/')    
    for hostname_file in json_rootDir.iterdir():
        hostname = re.sub(r'nxos_json_data\S', '',str(hostname_file))
        inFile = json_rootDir / hostname
        with open(inFile) as f:
            newFile=f.read().replace('Eth', 'Ethernet')
        with open(inFile, 'w') as f:
            f.write(newFile)
        with open(inFile) as f:
            newFile=f.read().replace('Po', 'port-channel')
        with open(inFile, 'w') as f:
            f.write(newFile)

def combine_yamlFiles(dev_dict1, dev_dict2, devType='border'):
    # Combine L2 Vlans
    tmplL2Vlans_dict1 = dev_dict1['cs_conf_vlans'].copy()
    tmplL2Vlans_dict2 = dev_dict2['cs_conf_vlans'].copy()
    tmplL2Vlans_dict3 = dev_dict1['tenants']['acmegrp']['l2vlans'].copy()
    tmplL2Vlans_dict4 = dev_dict2['tenants']['acmegrp']['l2vlans'].copy()
    tmplL2Vlans_resultDict = {**tmplL2Vlans_dict1, **tmplL2Vlans_dict2}
    tmplL2Vlans_resultDict2 = {**tmplL2Vlans_dict3, **tmplL2Vlans_dict4}
    devSvis_list = []
    vrfs_exc_list = [] 
    for dev1_vrf in dev_dict1['tenants']['acmegrp']['vrfs']:
        for dev1_svi in dev_dict1['tenants']['acmegrp']['vrfs'][dev1_vrf]['svis']:
            devSvis_list.append(dev1_svi)
    for dev2_vrf in dev_dict2['tenants']['acmegrp']['vrfs']:
        # Combine VRFs
        if dev2_vrf not in dev_dict1['tenants']['acmegrp']['vrfs']:
            dev_dict1['tenants']['acmegrp']['vrfs'][dev2_vrf] = dev_dict2['tenants']['acmegrp']['vrfs'][dev2_vrf].copy()
            vrfs_exc_list.append(dev2_vrf)
        # Combine Static Routes
        elif dev2_vrf in dev_dict1['tenants']['acmegrp']['vrfs'] and devType=='dis':
            for dev2_staticRoute_list in dev_dict2['tenants']['acmegrp']['vrfs'][dev2_vrf]['static_routes']:
                dev_dict1['tenants']['acmegrp']['vrfs'][dev2_vrf]['static_routes'].append(dev2_staticRoute_list)   
        # Combine SVIs
        for dev2_svi in dev_dict2['tenants']['acmegrp']['vrfs'][dev2_vrf]['svis']:   
            if dev2_svi not in dev_dict1['tenants']['acmegrp']['vrfs'][dev2_vrf]['svis']:
                dev_dict1['tenants']['acmegrp']['vrfs'][dev2_vrf]['svis'][dev2_svi] = dev_dict2['tenants']['acmegrp']['vrfs'][dev2_vrf]['svis'][dev2_svi].copy()

    dev_dict1['cs_conf_vlans'] = tmplL2Vlans_resultDict.copy()
    dev_dict1['tenants']['acmegrp']['l2vlans'] = tmplL2Vlans_resultDict2.copy()
    dev_dict1['cs_conf_vlan_interfaces'] = dev_dict2['cs_conf_vlan_interfaces'].copy()
    
    # Combine ACLs
    for dev2_acl in dev_dict2['cs_conf_access_lists']:
        if dev2_acl not in dev_dict1['cs_conf_access_lists']:
            dev_dict1['cs_conf_access_lists'][dev2_acl] = dev_dict2['cs_conf_access_lists'][dev2_acl].copy()

    # Combine VLAN Interfaces (cli conf gen)
    for dev2_vlanIf in dev_dict2['cs_conf_vlan_interfaces']:
        if dev2_vlanIf not in dev_dict1['cs_conf_vlan_interfaces']:
            dev_dict1['cs_conf_vlan_interfaces'][dev2_vlanIf] = dev_dict2['cs_conf_vlan_interfaces'][dev2_vlanIf]
    for empty_vlanIf in dev_dict1['cs_conf_vlan_interfaces'].copy():
        if dev_dict1['cs_conf_vlan_interfaces'][empty_vlanIf] == {}:
            dev_dict1['cs_conf_vlan_interfaces'].pop(empty_vlanIf, None)

    # Combine OSPF processes
    if devType == 'border':
        processId_len = len(dev_dict1['cs_conf_router_ospf']['process_ids'])
        for processId in dev_dict2['cs_conf_router_ospf']['process_ids']:
            for vrf_exc in vrfs_exc_list:
                if dev_dict2['cs_conf_router_ospf']['process_ids'][processId]['vrf'] == vrf_exc:
                    processId_len = processId_len + 1
                    dev_dict1['cs_conf_router_ospf']['process_ids'][str(processId_len)] = dev_dict2['cs_conf_router_ospf']['process_ids'][processId].copy()   
        
        # Combine Route-Maps
        for dev2_routeMap in dev_dict2['cs_conf_route_maps']:
            if dev2_routeMap not in dev_dict1['cs_conf_route_maps']:
                dev_dict1['cs_conf_route_maps'][dev2_routeMap] = dev_dict2['cs_conf_route_maps'][dev2_routeMap].copy()

        # Combine prefix lists
        for dev2_prefixL in dev_dict2['cs_conf_prefix_lists']:
            if dev2_prefixL not in dev_dict1['cs_conf_prefix_lists']:
                dev_dict1['cs_conf_prefix_lists'][dev2_prefixL] = dev_dict2['cs_conf_prefix_lists'][dev2_prefixL].copy()  
    else:
        pass    

    return dev_dict1

def add_coreSubIfs(dcId, file, platform='7050CX3'):
    data_dir = Path('data/')
    subIfs_dir = data_dir / file
    subIfs_list = read_csv_subIfs(subIfs_dir)
    l3_ifs = []
    for subIfs in subIfs_list:
        tmpl3_ifs_dictList = {}
        tmpl3_ifs_dictList[subIfs['vrf']] = []
        subIf_dict1 = {}
        subIf_dict1['nodes'] = ['swex-'+ dcId +'-bl01a', 'swex-'+ dcId +'-bl01b']
        if platform == '7050CX3':
            subIf_dict1['interfaces'] = ['Ethernet29.' +  subIfs['vlanId'], 'Ethernet29.' +  subIfs['vlanId']]
        elif platform == '7050SX3':
            subIf_dict1['interfaces'] = ['Ethernet53/1.' +  subIfs['vlanId'], 'Ethernet53/1.' +  subIfs['vlanId']]
        subIf_dict1['ip_addresses']= subIfs['ethip1']
        subIf_dict1['description'] = subIfs['vrf'] + '_to_core1'
        subIf_dict1['enabled'] = bool(False)
        subIf_dict1['mtu'] = 1500
        subIf_dict1['raw_eos_cli'] = '''ip ospf area 0.0.0.0  
                                        ip ospf network point-to-point'''
        tmpl3_ifs_dictList[subIfs['vrf']].append(subIf_dict1)
        subIf_dict2 = {}
        subIf_dict2['nodes'] = ['swex-'+ dcId +'-bl01a', 'swex-'+ dcId +'-bl01b']
        if platform == '7050CX3':
            subIf_dict2['interfaces'] = ['Ethernet30.' +  subIfs['vlanId'], 'Ethernet30.' +  subIfs['vlanId']]
        elif platform == '7050SX3':
            subIf_dict2['interfaces'] = ['Ethernet54/1.' +  subIfs['vlanId'], 'Ethernet54/1.' +  subIfs['vlanId']]
        subIf_dict2['ip_addresses']= subIfs['ethip2']
        subIf_dict2['description'] = subIfs['vrf'] + '_to_core2'
        subIf_dict2['enabled'] = bool(False)
        subIf_dict2['mtu'] = 1500
        subIf_dict2['raw_eos_cli'] = 'ip ospf area 0.0.0.0'
        tmpl3_ifs_dictList[subIfs['vrf']].append(subIf_dict2)
        l3_ifs.append(tmpl3_ifs_dictList)
    return l3_ifs

def create_leafs_varsFile():
    groupVars_dir = Path('group_vars')
    rmv_keys = ['cs_conf_prefix_lists', 'cs_conf_route_maps', 'cs_conf_router_ospf', ]
    for dev_groupVars_path in groupVars_dir.iterdir():
        if PurePath(str(dev_groupVars_path)).match('*border.yml'):
            border_groupVars = str(dev_groupVars_path).replace(str(groupVars_dir),'')[1:]
            dcId_groupVars = border_groupVars.replace('_border.yml','')
            leaf_groupVar = dcId_groupVars + '_leaf.yml'
            leafPair_path = groupVars_dir / leaf_groupVar
            leafPair_path.write_bytes(dev_groupVars_path.read_bytes())
    for dev_groupVars_path in groupVars_dir.iterdir():
        if PurePath(str(dev_groupVars_path)).match('*leaf*.yml'):
            leaf_dict = load_yamlFile(dev_groupVars_path)    
            for vrf_tmp in leaf_dict['tenants']['acmegrp']['vrfs'].copy():
                if 'l3_interfaces' in leaf_dict['tenants']['acmegrp']['vrfs'][vrf_tmp]:
                    leaf_dict['tenants']['acmegrp']['vrfs'][vrf_tmp].pop('l3_interfaces', None)
                else:
                    pass
                if 'static_routes' in leaf_dict['tenants']['acmegrp']['vrfs'][vrf_tmp]:
                    leaf_dict['tenants']['acmegrp']['vrfs'][vrf_tmp].pop('static_routes', None)
                else:
                    pass
            for key in rmv_keys:
                if key in leaf_dict:
                    leaf_dict.pop(key, None)
                else:
                    pass
            with open(dev_groupVars_path, 'w+') as leafFile:
                dump(leaf_dict, leafFile, default_flow_style=False, width=1000, Dumper=NoAliasDumper)  

def main():
    """Main Program"""
    ### FOLDER STRUCTURE VARIABLES ###
    yaml_dir = Path('yaml_data/')
    fabric_dir = Path('group_vars/')
    run_data_dir = Path('nxos_conf/')
    
    ### SCRIPT VARIABLES ###
    host_list = []
    ifs_stage_dict = {}
    #host_list = ['swex-dc01-dis3','swex-dc01-dis4', 'swex-dc02-dis3','swex-dc02-dis4', 'swex-dh01-dis3','swex-dh01-dis4']
    dc01vlan_list = []
    dc02vlan_list = []
    dh01vlan_list = []
    dc01blVlan_list = []
    dc02blVlan_list = []
    dh01blVlan_list = []

    """ Reformat Interface Status Port Names """
    ### ONLY NEEDED ONCE AFTER CAPTURING THE INTERFACE STATUS OUTPUT ###
    print('If Interface Data needs to be reformated, quit and add "format_json_data" as an argument')
    if len (sys.argv) == 2:
        doFormat = sys.argv[1].lower()
        if doFormat == 'format_json_data' :
            replace_ifName()
    else:
        pass

    """Delete YAML files """
    print('Deleting staging YAML data...')
    del_yamlFiles(yaml_dir)
    
    """ Parse Running Configuration Outputs into Dictionaries """
    ### GET RUNNING CONFIGURATIONS PER HOST AND TRANSFER TO AN OBJECT ###
    for hostname_dir in run_data_dir.iterdir():
        hostname = re.sub(r'nxos_conf\S', '',str(hostname_dir))
        host_list.append(hostname)

    for host in host_list:
        ### CREATE THE FOLDER STRUCTURE AND INITIALIZE THE MAIN DICTIONARY ###
        parse_source_path = run_data_dir / host
        parsed_stage_dict = {}
        parsed_stage_dict['tenants'] = {}
        parsed_stage_dict['tenants']['acmegrp'] = {}
        parsed_stage_dict['tenants']['acmegrp']['mac_vrf_vni_base'] = 10000
        parsed_stage_dict['tenants']['acmegrp']['enable_mlag_ibgp_peering_vrfs'] = bool(True)
        parsed_stage_dict['tenants']['acmegrp']['vrfs'] = {}
        dcId_string = re.findall(r'-(\S+)-', host) 
        dcId = dcId_string[0]
        ### CREATE PARSE OBJECT ###
        confParse_file = CiscoConfParse(parse_source_path)

        """ Create a List of Unused Interfaces for Later removal """
        unusedIfs_list = []
        json_rootDir = Path('nxos_json_data/') 
        host_json = host + '.json'
        inFile = json_rootDir / host_json
        ### SEARCH IN FILE WITH PARSED SHOW INT STATUS OUTPUT ###
        with open(inFile) as f:
            ifStatus_jsonDict = json.load(f)
        for ifStatus in ifStatus_jsonDict:
            if ifStatus['status'] != 'connected':
                unusedIfs_list.append(ifStatus['port'])

        """ Parse VRFs """
        confParsed_vrfs = confParse_file.find_objects(r"^vrf context ")
        vrf_length = len(confParsed_vrfs)
        ### ADD MANUALLY ACME-GENERAL VRF ###
        parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL'] = {}
        parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'] = {}
        ### THE BELOW CAN ONLY USED TO TRANSFORM THE DATA GIVEN THAT THE VNI COULD VARY ###

        for confParsed_vrf_obj in confParsed_vrfs:
            vrf_id = (str(confParsed_vrf_obj.text).replace('vrf context ', ''))
            parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id] = {}
            parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id]['svis'] = {}

        """ Parse SVIs """
        ### INITIALIZE TEMP DICTIONARY TO EASE TRANSITION TO EOS_DESIGNS FORMAT ###
        svi_attr_dict = {}
        ### INITIALIZE SVI LIST TO BE USED TO COMPARE WITH L2 ONLY VLANS ###
        svi_list = []
        ### INITIALIZE CLI_CONF_GEN DICTIONARY FOR ADDITIONAL CONFIGURATIONS ###
        parsed_stage_dict['cs_conf_vlan_interfaces'] = {}
        confParsed_svis = confParse_file.find_objects(r"^interface V")
        ### GET INTERFACE VLAN ATTRIBUTES FROM CONFIG AND ATTACH TO TMP DICT ###
        for confParsed_svi_obj in confParsed_svis:
            svi_id = (str(confParsed_svi_obj.text).replace('interface Vlan', ''))
            svi_id = int(svi_id)
            svi_list.append(svi_id)
            svi_attr_dict[svi_id] = []
            for svi_ifch_obj in confParsed_svi_obj.children:
                svi_attr_dict[svi_id].append(str(svi_ifch_obj.text))
                for svi_ifgrandch_obj in svi_ifch_obj.children: 
                    svi_attr_dict[svi_id].append(str(svi_ifgrandch_obj.text))
        ### PARSE ALL CONFIGS IN INTERFACES ##
        for svi in svi_attr_dict:
            parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)] = {}
            vrf_string = 'vrf member'
            vrf_memberString = [vrf for vrf in svi_attr_dict[svi] if vrf_string in vrf]
            sviDesc_string = 'description'
            sviDesc_memberString = [sviDesc for sviDesc in svi_attr_dict[svi] if sviDesc_string in sviDesc]
            sviIpAdd_string = 'ip address'
            sviIpAdd_memberString = [sviIpAdd for sviIpAdd in svi_attr_dict[svi] if sviIpAdd_string in sviIpAdd]
            sviVipAdd_subString = 'ip'
            sviVipAdd_memberStrings = [sviVipAdd for sviVipAdd in svi_attr_dict[svi] if sviVipAdd_subString in sviVipAdd]
            sviIpHelper_string = 'ip dhcp relay address'
            sviIpHelper_memberStrings = [sviIpHelper for sviIpHelper in svi_attr_dict[svi] if sviIpHelper_string in sviIpHelper]
            sviPVlan_string = 'private-vlan'
            sviPVlan_memberString = [sviPVlan for sviPVlan in svi_attr_dict[svi] if sviPVlan_string in sviPVlan]
            sviAclGroup_string = 'ip access-group'
            sviAclGroup_memberString = [sviAclGroup for sviAclGroup in svi_attr_dict[svi] if sviAclGroup_string in sviAclGroup]
            #sviOspf_string = 'ip router ospf'
            #sviOspf_memberString = [sviOspf for sviOspf in svi_attr_dict[svi] if sviOspf_string in sviOspf]
            if vrf_memberString: 
                vrf_inMembership = re.findall(r'\s+vrf\smember\s+(\S+)', vrf_memberString[0])
                parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi] = {}
                parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['enabled'] = bool(False)
                parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['tags'] = [dcId]

                if sviDesc_memberString:
                    sviDesc = re.findall(r'\s+description\s(\S+)', sviDesc_memberString[0])
                    parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['name'] = sviDesc[0]
                else:
                    parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['name'] = 'unnamed_' + str(svi) 
                if sviIpAdd_memberString:
                    sviIpAddressMask = re.findall(r'\s+ip\saddress\s\d+.\d+.\d+.\d+(\S+)', sviIpAdd_memberString[0])
                if sviVipAdd_memberStrings:   
                    for sviVipAdd_memberString in sviVipAdd_memberStrings:
                        sviVipAdd = re.findall(r'\s+ip\s(\d+\.\d+\.\d+\.\d+)', sviVipAdd_memberString)
                        if sviVipAdd:
                            parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['ip_address_virtual'] = sviVipAdd[0] + sviIpAddressMask[0]
                if sviIpHelper_memberStrings:
                    parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['ip_helpers'] = {}
                    for sviIpHelper_memberString in sviIpHelper_memberStrings:
                        sviIpHelpers = re.findall(r'\s+ip\sdhcp\srelay\saddress\s(\S+)', sviIpHelper_memberString)
                        for sviIpHelper in sviIpHelpers:
                            parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_inMembership[0]]['svis'][svi]['ip_helpers'][sviIpHelper] = {}
                if sviPVlan_memberString:
                    sviPVlan = re.findall(r'\s+private-vlan\smapping\s(\S+)', sviPVlan_memberString[0])
                    parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['pvlan_mapping'] = sviPVlan[0]
                if sviAclGroup_memberString:
                    sviAclGroupName = re.findall(r'\s+ip\saccess-group\s(\S+)', sviAclGroup_memberString[0])
                    sviAclGroupDir = re.findall(r'\s+ip\saccess-group\s\S+\s(\w+)', sviAclGroup_memberString[0])
                    if sviAclGroupDir[0] == 'in':
                        parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['access_group_in'] = sviAclGroupName[0]
                    elif sviAclGroupDir[0] == 'out':
                        parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['access_group_out'] = sviAclGroupName[0] 
                #if sviOspf_memberString:
                #    sviOspfArea = re.findall(r'\s+ip\srouter\sospf\s\d+\sarea\s(\S+)', sviOspf_memberString[0])
                #    parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['ospf_area'] = sviOspfArea[0]
            else:
                if sviDesc_memberString:
                    sviDesc = re.findall(r'\s+description\s(\S+)', sviDesc_memberString[0])
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi] = {}
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['name'] = sviDesc[0]
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['enabled'] = bool(False)
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['tags'] = [dcId]
                else:
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi] = {}
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['name'] = 'unnamed_' + str(svi) 
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['enabled'] = bool(False)
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['tags'] = [dcId]
                if sviIpAdd_memberString:
                    sviIpAddMask = re.findall(r'\s+ip\saddress\s\d+.\d+.\d+.\d+(\S+)', sviIpAdd_memberString[0])
                if sviVipAdd_memberStrings:   
                    for sviVipAdd_memberString in sviVipAdd_memberStrings:
                        sviVipAdd = re.findall(r'\s+ip\s(\d+\.\d+\.\d+\.\d+)', sviVipAdd_memberString)
                        if sviVipAdd:
                            parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['ip_address_virtual'] = sviVipAdd[0] + sviIpAddMask[0]
                if sviIpHelper_memberStrings:
                    parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['ip_helpers'] = {}
                    for sviIpHelper_memberString in sviIpHelper_memberStrings:
                        sviIpHelpers = re.findall(r'\s+ip\sdhcp\srelay\saddress\s(\S+)', sviIpHelper_memberString)
                        for sviIpHelper in sviIpHelpers:
                            parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['svis'][svi]['ip_helpers'][sviIpHelper] = {}
                           
                if sviPVlan_memberString:
                    sviPVlan = re.findall(r'\s+private-vlan\smapping\s(\S+)', sviPVlan_memberString[0])
                    parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['pvlan_mapping'] = sviPVlan[0]
                if sviAclGroup_memberString:
                    sviAclGroupName = re.findall(r'\s+ip\saccess-group\s(\S+)', sviAclGroup_memberString[0])
                    sviAclGroupDir = re.findall(r'\s+ip\saccess-group\s\S+\s(\w+)', sviAclGroup_memberString[0])
                    if sviAclGroupDir[0] == 'in':
                        parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['access_group_in'] = sviAclGroupName[0]
                    elif sviAclGroupDir[0] == 'out':
                        parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['access_group_out'] = sviAclGroupName[0]
                #if sviOspf_memberString:
                #    sviOspfArea = re.findall(r'\s+ip\srouter\sospf\s\d+\sarea\s(\S+)', sviOspf_memberString[0])
                #    parsed_stage_dict['cs_conf_vlan_interfaces']['Vlan'+ str(svi)]['ospf_area'] = sviOspfArea[0]
        ### REMOVE EMPTY SVIS ###
        for emptySvi in parsed_stage_dict['cs_conf_vlan_interfaces'].copy():
            if parsed_stage_dict['cs_conf_vlan_interfaces'][emptySvi] == {}:
                parsed_stage_dict['cs_conf_vlan_interfaces'].pop(emptySvi, None)

        """ Parse Static Routes """  
        ### GLOBAL ROUTING TABLE STATIC ROUTES ###      
        confParsed_globStaticRoute = confParse_file.find_objects(r"^ip route")  
        parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['static_routes'] = []
        for confParsed_globStaticRoute_obj in confParsed_globStaticRoute:
            globStaticRoutes_tmpDict = {}
            globStaticRoutes_tmpDict['nodes'] = []
            globStaticRoute_string = str(confParsed_globStaticRoute_obj.text)
            globStaticRouteDest_string = re.findall(r'^ip\sroute\s(\S+).*', globStaticRoute_string)
            globStaticRouteNextHopIf_string = re.findall(r'^ip\sroute\s\S+\s\S+\s(\S+).*', globStaticRoute_string)
            globStaticRouteNextHopIp_string = re.findall(r'^ip\sroute\s\S+\s(\d+.\d+.\d+.\d+).*', globStaticRoute_string)
            globStaticRouteNameIf_string =re.findall(r'^ip\sroute\s\S+\s\S+\s\S+\sname\s(.*)', globStaticRoute_string)
            globStaticRouteNameIp_string = re.findall(r'^ip\sroute\s\S+\s\S+\sname\s(.*)', globStaticRoute_string)
            globStaticInterfaceIf_string =re.findall(r'^ip\sroute\s\S+\s(\S+)\s\S+\s.*', globStaticRoute_string)
            if globStaticRouteDest_string:
                globStaticRoutes_tmpDict['destination_address_prefix'] = globStaticRouteDest_string[0]
                if dcId == 'dc01':
                    globStaticRoutes_tmpDict['nodes']= ['swex-dc01-bl01a','swex-dc01-bl01b']
                elif dcId == 'dc02':
                    globStaticRoutes_tmpDict['nodes']= ['swex-dc02-bl01a','swex-dc02-bl01b']
                elif dcId == 'dh01':
                    globStaticRoutes_tmpDict['nodes']= ['swex-dh01-bl01a','swex-dh01-bl01b']
            if globStaticRouteNextHopIf_string:
                globStaticRoutes_tmpDict['gateway'] = globStaticRouteNextHopIf_string[0]
            elif globStaticRouteNextHopIp_string:
                globStaticRoutes_tmpDict['gateway'] = globStaticRouteNextHopIp_string[0]
            if globStaticRouteNameIf_string:
                globStaticRoutes_tmpDict['name'] = globStaticRouteNameIf_string[0].replace('(','').replace(')','')
            elif globStaticRouteNameIp_string:
                globStaticRoutes_tmpDict['name'] = globStaticRouteNameIp_string[0].replace('(','').replace(')','')
            if globStaticInterfaceIf_string:
                globStaticRoutes_tmpDict['interface'] = globStaticInterfaceIf_string[0]
            parsed_stage_dict['tenants']['acmegrp']['vrfs']['ACME-GENERAL']['static_routes'].append(globStaticRoutes_tmpDict) 
                
        ### VRF SPECIFIC STATIC ROUTES ###          
        for confParsed_vrfRoute_obj in confParsed_vrfs: 
            vrf_id = (str(confParsed_vrfRoute_obj.text).replace('vrf context ', ''))
            parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id]['static_routes'] = []
            for vrfRoute_ch_obj in confParsed_vrfRoute_obj.children:
                vrfStaticRoute_tmpDict = {} 
                vrfStaticRoute_tmpDict['nodes'] = []
                vrfStaticRoute_string = str(vrfRoute_ch_obj.text)
                vrfStaticRoutedestNw_string = re.findall(r'ip\sroute\s(\d+\.\d+\.\d+\.\d+/\d+).*', vrfStaticRoute_string )
                vrfStaticRouteNextHopIf_string = re.findall(r'ip\sroute\s\S+\s\S+\s(\d+\.\d+\.\d+\.\d+).*', vrfStaticRoute_string )
                vrfStaticRouteNextHopIp_string = re.findall(r'ip\sroute\s\S+\s(\d+\.\d+\.\d+\.\d+).*', vrfStaticRoute_string )
                vrfStaticRouteNameIf_string =re.findall(r'ip\sroute\s\S+\s\S+\s\S+\sname\s(.*)', vrfStaticRoute_string)
                vrfStaticRouteNameIp_string = re.findall(r'ip\sroute\s\S+\s\S+\sname\s(.*)', vrfStaticRoute_string)
                vrfStaticInterfaceIf_string =re.findall(r'ip\sroute\s\S+\s(?!\d+\.\d+\.\d+\.\d+)(\S+).*', vrfStaticRoute_string)
                if vrfStaticRoutedestNw_string:
                    vrfStaticRoute_tmpDict['destination_address_prefix'] = vrfStaticRoutedestNw_string[0]
                    if dcId == 'dc01':
                        vrfStaticRoute_tmpDict['nodes']= ['swex-dc01-bl01a','swex-dc01-bl01b']
                    elif dcId == 'dc02':
                        vrfStaticRoute_tmpDict['nodes']= ['swex-dc02-bl01a','swex-dc02-bl01b']
                    elif dcId == 'dh01':
                        vrfStaticRoute_tmpDict['nodes']= ['swex-dh01-bl01a','swex-dh01-bl01b']
                if vrfStaticRoutedestNw_string:   
                    if vrfStaticInterfaceIf_string and vrfStaticRouteNameIf_string:
                        vrfStaticRoute_tmpDict['gateway'] = vrfStaticRouteNextHopIf_string[0]
                        vrfStaticRoute_tmpDict['name'] = vrfStaticRouteNameIf_string[0].replace('(','').replace(')','')
                        vrfStaticRoute_tmpDict['interface'] = vrfStaticInterfaceIf_string[0]
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id]['static_routes'].append(vrfStaticRoute_tmpDict)
                    elif vrfStaticInterfaceIf_string and not vrfStaticRouteNameIf_string:
                        vrfStaticRoute_tmpDict['gateway'] = vrfStaticRouteNextHopIf_string[0]
                        vrfStaticRoute_tmpDict['interface'] = vrfStaticInterfaceIf_string[0]
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id]['static_routes'].append(vrfStaticRoute_tmpDict)
                    elif vrfStaticRouteNextHopIp_string and vrfStaticRouteNameIp_string:
                        vrfStaticRoute_tmpDict['gateway'] = vrfStaticRouteNextHopIp_string[0]
                        vrfStaticRoute_tmpDict['name'] = vrfStaticRouteNameIp_string[0].replace('(','').replace(')','')
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id]['static_routes'].append(vrfStaticRoute_tmpDict)
                    elif vrfStaticRouteNextHopIp_string and not vrfStaticRouteNameIp_string:
                        vrfStaticRoute_tmpDict['gateway'] = vrfStaticRouteNextHopIp_string[0]
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_id]['static_routes'].append(vrfStaticRoute_tmpDict)
                else:
                    pass
        """ Add Core Sub Interfaces """
        ### GET DATA FROM CSV FILE ###
        blDcId = dcId[:2] + '0' + dcId[2:]
        dc01subIfs_file = 'dc01vrfsToCore.csv'
        dc01subIfs_dictList = add_coreSubIfs(blDcId, dc01subIfs_file)
        dc02subIfs_file = 'dc02vrfsToCore.csv'
        dc02subIfs_dictList = add_coreSubIfs(blDcId, dc02subIfs_file)
        dh01subIfs_file = 'dh01vrfsToCore.csv'
        dh01subIfs_dictList = add_coreSubIfs(blDcId, dh01subIfs_file,'7050SX3')
        dc01cnSubIfs_file = 'dc01cnvrfsToCore.csv'
        dc01cnSubIfs_dictList = add_coreSubIfs(blDcId,dc01cnSubIfs_file)
        dc02cnSubIfs_file = 'dc02cnvrfsToCore.csv'
        dc02cnSubIfs_dictList = add_coreSubIfs(blDcId, dc02cnSubIfs_file)
        ### APPEND SUB-IFS OUTPUT TO L3_INTERFACES ON MAIN DICT ###
        if '-dis' in host:
            if dcId == 'dc01':
                for dc01subIfs in dc01subIfs_dictList:
                    for vrf in dc01subIfs:
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf]['l3_interfaces'] = dc01subIfs[vrf]
            elif dcId == 'dc02':
                for dc02subIfs in dc02subIfs_dictList:
                    for vrf in dc02subIfs:
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf]['l3_interfaces'] = dc02subIfs[vrf]
            elif dcId == 'dh01':
                for dh01subIfs in dh01subIfs_dictList:
                    for vrf in dh01subIfs:
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf]['l3_interfaces'] = dh01subIfs[vrf]
        if '-cn' in host:
            if dcId == 'dc01':
                for dc01cnSubIfs in dc01cnSubIfs_dictList:
                    for vrf in dc01cnSubIfs:
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf]['l3_interfaces'] = dc01cnSubIfs[vrf]
            if dcId == 'dc02':
                for dc02cnSubIfs in dc02cnSubIfs_dictList:
                    for vrf in dc02cnSubIfs:
                        parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf]['l3_interfaces'] = dc02cnSubIfs[vrf]

        """ Parse VLANs """
        ### INITIALIZE TMP DICTS TO GET ALL VLANS CONFIGURED ###
        allVlans_tmpAttr_dict = {}
        allVlans_attr_dict = {}
        allVlans_attr_tranDict = {}
        parsed_stage_dict['cs_conf_vlans'] = {}
        vlanRanges_list = []
        ### PARSE ALL VLANS CONFIGURATIONS ###
        confParsed_vlans = confParse_file.find_objects(r"^vlan\s")
        parsed_stage_dict['cs_conf_vlans'] = {}
        parsed_stage_dict['tenants']['acmegrp']['l2vlans'] = {}
        for confParsed_vlan_obj in confParsed_vlans: 
            vlanId_strings = (str(confParsed_vlan_obj.text)).replace('vlan ', '') 
            ### PARSE VLANS NOT IN RANGES ###
            if '-' not in vlanId_strings:
                vlanId_string = re.findall(r'(\d+)', vlanId_strings)
                vlanId = vlanId_string[0]
                allVlans_tmpAttr_dict[vlanId] = []
                allVlans_attr_dict[vlanId] = {}
                if dcId == 'dc01':
                    dc01vlan_list.append(int(vlanId))
                elif dcId == 'dc02':
                    dc02vlan_list.append(int(vlanId))
                elif dcId == 'dh01':
                    dh01vlan_list.append(int(vlanId))

            ### PARSE VLANS IN RANGES ###
            elif '-' in vlanId_strings:
                vlanId_string = re.findall(r'^(\d+-\d+)(?!.+)', vlanId_strings)
                if vlanId_string:
                    vlanId = vlanId_string[0]
                    vlanRanges_list.append(vlanId)
                    allVlans_tmpAttr_dict[vlanId] = []
                    allVlans_attr_dict[vlanId] = {}
            for vlan_nameCh_obj in confParsed_vlan_obj.children:
                allVlans_tmpAttr_dict[vlanId].append(str(vlan_nameCh_obj.text))
        ### ATTACH PRIVATE VLANS AND NAMES ###
        for vlanId in allVlans_tmpAttr_dict:  
            vName_string = 'name'
            vName_memberString = [vName for vName in allVlans_tmpAttr_dict[vlanId] if vName_string in vName]
            pVlanIsolated_string = 'private-vlan isolated'
            pVlanIsolated_memberString = [pVlanIsolated for pVlanIsolated in allVlans_tmpAttr_dict[vlanId] if pVlanIsolated_string in pVlanIsolated]
            pVlanPrimary_string = 'private-vlan association'
            pVlanPrimary_memberString = [pVlanPrimary for pVlanPrimary in allVlans_tmpAttr_dict[vlanId] if pVlanPrimary_string in pVlanPrimary]
            if vName_memberString:
                vName = re.findall(r'\s+name\s(\S+)', vName_memberString[0])
                allVlans_attr_dict[vlanId]['name'] = vName[0]
            elif not vName_memberString:
                allVlans_attr_dict[vlanId]['name'] = 'unnamed'
            if pVlanIsolated_memberString:
                allVlans_attr_dict[vlanId]['private_vlan'] = {}
                allVlans_attr_dict[vlanId]['private_vlan']['type'] = 'isolated'
                allVlans_attr_dict[vlanId]['private_vlan']['primary_vlan'] = ''
            if pVlanPrimary_memberString:
                pVlanAssoc = re.findall(r'\s+private-vlan\sassociation\s(\S+)', pVlanPrimary_memberString[0])
                allVlans_attr_dict[vlanId]['private_vlan'] = {}
                allVlans_attr_dict[vlanId]['private_vlan']['primary_association'] = pVlanAssoc[0]

        ### SEPARATE VLAN RANGES INTO INDIVIDUAL VLANS ###
        allVlans_attr_tranDict = allVlans_attr_dict.copy()
        for vlanRange in vlanRanges_list:
            allVlans_attr_tranDict.pop(vlanRange, None)
        for vlanRange in allVlans_attr_dict:
            if '-' in vlanRange:
                vlanRange_startString = re.findall(r'(\d+)-', vlanRange)
                vlanRange_start = int(vlanRange_startString[0])
                vlanRange_stopString =  re.findall(r'\d+-(\d+)', vlanRange)  
                vlanRange_stop = int(vlanRange_stopString[0])
                for vlanId in range(vlanRange_start, vlanRange_stop + 1):
                    allVlans_attr_tranDict[str(vlanId)] = allVlans_attr_dict[vlanRange].copy()
                    if dcId == 'dc01':
                        dc01vlan_list.append(int(vlanId))
                    elif dcId == 'dc02':
                        dc02vlan_list.append(int(vlanId))
                    elif dcId == 'dh01':
                        dh01vlan_list.append(int(vlanId))
        #### COMPARE ALL VLANS WITH VLANS WITH SVIS AND REMOVE THOSE WITH SVIS ###
        for svi in svi_list:
            if 'private_vlan' not in allVlans_attr_tranDict[str(svi)]:
                allVlans_attr_tranDict.pop(str(svi), None)
        ### ADD ALL VLANS WITH PRIVATE VLAN CONFIGS TO MAIN DICTIONARY ###
        for pVlans in allVlans_attr_tranDict:
            if 'private_vlan' in allVlans_attr_tranDict[pVlans]:
                parsed_stage_dict['cs_conf_vlans'][int(pVlans)] = allVlans_attr_tranDict[pVlans].copy()
                parsed_stage_dict['tenants']['acmegrp']['l2vlans'][int(pVlans)] = {}
                parsed_stage_dict['tenants']['acmegrp']['l2vlans'][int(pVlans)]['name'] = allVlans_attr_tranDict[pVlans]['name']
            elif 'private_vlan' not in allVlans_attr_tranDict[pVlans]:
                parsed_stage_dict['tenants']['acmegrp']['l2vlans'][int(pVlans)] = allVlans_attr_tranDict[pVlans].copy()
        ### MOVE PRIVATE VLAN ASSOCIATION TO ISOLATED VLAN ###
        primaryPvlans_list = []
        for vlan_id in parsed_stage_dict['cs_conf_vlans']:
            if 'primary_association' in parsed_stage_dict['cs_conf_vlans'][vlan_id]['private_vlan']:
                primaryPvlans_list.append(vlan_id)
                vlan_primary_str = parsed_stage_dict['cs_conf_vlans'][vlan_id]['private_vlan']['primary_association']
                vlan_primary = int(vlan_primary_str)
                parsed_stage_dict['cs_conf_vlans'][vlan_primary]['private_vlan']['primary_vlan'] = vlan_id
        ### REMOVE PRIMARY VLAN KEY ###
        for primaryPvlan in primaryPvlans_list:
            parsed_stage_dict['cs_conf_vlans'][primaryPvlan].pop('private_vlan', None)
        ### MOVE PRIMARY VLANS TO DESIGNS ###
        for primaryPvlan in parsed_stage_dict['cs_conf_vlans']:
            if 'private_vlan' not in parsed_stage_dict['cs_conf_vlans'][primaryPvlan]:
                parsed_stage_dict['tenants']['acmegrp']['l2vlans'][primaryPvlan] = parsed_stage_dict['cs_conf_vlans'][primaryPvlan]
        for primaryPvlan in primaryPvlans_list:
            parsed_stage_dict['cs_conf_vlans'].pop(primaryPvlan, None)
        ### ADD VLANS TO DESIGNS FOR VNI AND BGP CREATION ###
        isolatedVlans_list = []
        for isolatedVlan in parsed_stage_dict['cs_conf_vlans']:
             isolatedVlans_list.append(isolatedVlan)
        for isolatedVlan in isolatedVlans_list:
            parsed_stage_dict['tenants']['acmegrp']['l2vlans'][isolatedVlan]= {}
            parsed_stage_dict['tenants']['acmegrp']['l2vlans'][isolatedVlan]['name'] = parsed_stage_dict['cs_conf_vlans'][isolatedVlan]['name']
        ### REMOVE VLANS THAT HAVE AN SVI FROM L2VLANS ###  
        for svi in svi_list:
            parsed_stage_dict['tenants']['acmegrp']['l2vlans'].pop(svi, None)
        ### RENAME UNNAMED VLANS ###
        for l2vlan in parsed_stage_dict['tenants']['acmegrp']['l2vlans']:
            parsed_stage_dict['tenants']['acmegrp']['l2vlans'][l2vlan]['tags'] = [dcId]
            if parsed_stage_dict['tenants']['acmegrp']['l2vlans'][l2vlan]['name'] == 'unnamed':
                parsed_stage_dict['tenants']['acmegrp']['l2vlans'][l2vlan]['name'] = 'unnamed_' + str(l2vlan)
        
        """ Parse ACLs """
        confParsed_acls = confParse_file.find_objects(r"^ip access-list")
        parsed_stage_dict['cs_conf_access_lists'] = {}
        for confParsed_acl_obj in confParsed_acls:
            aclName_string = (str(confParsed_acl_obj.text)).replace('ip access-list ', '')
            parsed_stage_dict['cs_conf_access_lists'][aclName_string] = {}
            parsed_stage_dict['cs_conf_access_lists'][aclName_string]['sequence_numbers'] = {}
            for aclCh_obj in confParsed_acl_obj.children:
                seqNo_strings = re.findall(r'^\s+(\d+)', str(aclCh_obj.text))
                action_string = re.findall(r'^\s+\d+\s(.+)\s+', str(aclCh_obj.text))
                if seqNo_strings and action_string:
                    if 'portgroup' not in action_string[0]:
                        parsed_stage_dict['cs_conf_access_lists'][aclName_string]['sequence_numbers'][int(seqNo_strings[0])] = {}
                        parsed_stage_dict['cs_conf_access_lists'][aclName_string]['sequence_numbers'][int(seqNo_strings[0])]['action'] = action_string[0]
                    else:
                        pass
        parsed_stage_dict['cs_conf_access_lists'].pop('limit-admin', None)
        parsed_stage_dict['cs_conf_access_lists'].pop('management-servers-operator', None)
        parsed_stage_dict['cs_conf_access_lists'].pop('discovery-servers', None)

        """ Parse Route Maps"""
        confParsed_routeMaps = confParse_file.find_objects(r'^route-map ')
        parsed_stage_dict['cs_conf_route_maps'] = {}
        if '-dis' in host or '-cn' in host:
            parsed_stage_dict['cs_conf_route_maps']['BGP-TO-OSPF'] = {}
            parsed_stage_dict['cs_conf_route_maps']['BGP-TO-OSPF']['sequence_numbers'] = {}
            parsed_stage_dict['cs_conf_route_maps']['BGP-TO-OSPF']['sequence_numbers'][100] = {}
            parsed_stage_dict['cs_conf_route_maps']['BGP-TO-OSPF']['sequence_numbers'][100]['type'] = 'permit'
        for confParsed_routeMaps_obj in confParsed_routeMaps:
            routeMapName_string = re.findall(r'^route-map\s(\S+).*', str(confParsed_routeMaps_obj.text))
            routeMapSeq_string = re.findall(r'^route-map\s\S+\s\w+\s(\d+)', str(confParsed_routeMaps_obj.text))
            routeMapSeq = int(routeMapSeq_string[0])
            routeMapType_string = re.findall(r'^route-map\s\S+\s(\w+)+.*', str(confParsed_routeMaps_obj.text))
            if routeMapName_string[0] not in parsed_stage_dict['cs_conf_route_maps']:
                parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]] = {}
                parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'] = {}
                parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq] = {}
                parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['type'] = routeMapType_string[0]
            elif routeMapName_string[0] in parsed_stage_dict['cs_conf_route_maps']:
                parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq] = {}
                parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['type'] = routeMapType_string[0]
            for routeMapsCh_obj in confParsed_routeMaps_obj.children:
                routeMapSeqDesc_string = re.findall(r'description\s(.+)', str(routeMapsCh_obj.text))
                routeMapMatch_string = re.findall(r'match\s(.+)', str(routeMapsCh_obj.text))
                routeMapSet_string = re.findall(r'set\s(.+)', str(routeMapsCh_obj.text))
                if routeMapSeqDesc_string:
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['description'] = routeMapSeqDesc_string[0]
                if 'match' not in parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq] and routeMapMatch_string:
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['match'] = []  
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['match'].append(routeMapMatch_string[0])    
                elif 'match' in parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq] and routeMapMatch_string:
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['match'].append(routeMapMatch_string[0]) 
                if 'set' not in parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq] and routeMapSet_string:
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['set'] = []  
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['set'].append(routeMapSet_string[0])    
                elif 'set' in parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq] and routeMapSet_string:
                    parsed_stage_dict['cs_conf_route_maps'][routeMapName_string[0]]['sequence_numbers'][routeMapSeq]['set'].append(routeMapSet_string[0])         

        """ Parse Prefix Lists"""    
        confParsed_prefixLists = confParse_file.find_objects(r'^ip prefix-list ') 
        parsed_stage_dict['cs_conf_prefix_lists'] = {}
        for confParsed_prefixLists_obj in confParsed_prefixLists:
            prefixListName_string = re.findall(r'ip\sprefix-list\s(\S+).*', str(confParsed_prefixLists_obj.text))
            prefixListSeq_string = re.findall(r'ip\sprefix-list\s\S+\sseq\s(\d+).*', str(confParsed_prefixLists_obj.text))
            prefixListAct_string = re.findall(r'ip\sprefix-list\s\S+\sseq\s\d+\s(.+)', str(confParsed_prefixLists_obj.text))
            if prefixListName_string[0] not in parsed_stage_dict['cs_conf_prefix_lists']:
                prefixListSeq = int(prefixListSeq_string[0])
                parsed_stage_dict['cs_conf_prefix_lists'][prefixListName_string[0]] = {}        
                parsed_stage_dict['cs_conf_prefix_lists'][prefixListName_string[0]]['sequence_numbers'] = {}
                parsed_stage_dict['cs_conf_prefix_lists'][prefixListName_string[0]]['sequence_numbers'][prefixListSeq] = {}
                parsed_stage_dict['cs_conf_prefix_lists'][prefixListName_string[0]]['sequence_numbers'][prefixListSeq]['action'] = prefixListAct_string[0]
            elif prefixListName_string[0] in parsed_stage_dict['cs_conf_prefix_lists']:
                parsed_stage_dict['cs_conf_prefix_lists'][prefixListName_string[0]]['sequence_numbers'][prefixListSeq] = {}
                parsed_stage_dict['cs_conf_prefix_lists'][prefixListName_string[0]]['sequence_numbers'][prefixListSeq]['action'] = prefixListAct_string[0]

        """ Parse OSPF """
        ### INITIALIZE OSPF TMP DICT TO EASE TRANSITION TO MAIN DICT ###
        ospf_tmpAttr_dict = {}
        ospf_tmpAttr_dict['vrf'] = {}
        parsed_stage_dict['cs_conf_router_ospf'] = {}
        parsed_stage_dict['cs_conf_router_ospf']['process_ids'] = {}
        confParsed_ospf = confParse_file.find_objects(r'^router ospf ')
        for confParsed_ospf_obj in confParsed_ospf:
            for ospfCh_obj in confParsed_ospf_obj.children:
                ospfVrf_strings = re.findall(r'\s+vrf\s(\S+)', str(ospfCh_obj.text))
                if ospfVrf_strings:
                    for ospfGch_obj in ospfCh_obj.children:
                        if ospfVrf_strings[0] not in ospf_tmpAttr_dict['vrf']: 
                            ospf_tmpAttr_dict['vrf'][ospfVrf_strings[0]] = []
                            ospf_tmpAttr_dict['vrf'][ospfVrf_strings[0]].append(str(ospfGch_obj.text))
                        else:
                            ospf_tmpAttr_dict['vrf'][ospfVrf_strings[0]].append(str(ospfGch_obj.text))
                else:
                    if 'ACME-GENERAL' not in ospf_tmpAttr_dict['vrf']:
                        ospf_tmpAttr_dict['vrf']['ACME-GENERAL'] = []
                        ospf_tmpAttr_dict['vrf']['ACME-GENERAL'].append(str(ospfCh_obj.text))
                    else:
                        ospf_tmpAttr_dict['vrf']['ACME-GENERAL'].append(str(ospfCh_obj.text))
        num_ospfVrfs = len(ospf_tmpAttr_dict['vrf'])
        ### BELOW CAN ONLY BE USED ONCE SINCE THE PROCESS ID WOULD VARY ###
        ### PARSE OSPF CONFIGURATIONS AND ADD TO MAIN DICT ###
        for ospfVrf_key, ospf_processId in zip(ospf_tmpAttr_dict['vrf'], range(1, num_ospfVrfs+1)):
            ospfRouterId_subString = 'router-id'
            ospfRouterId_memberString = [ospfRouterId for ospfRouterId in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfRouterId_subString in ospfRouterId]
            ospfAreaData_subString = 'area'
            #ospfAreaData_memberStrings = [ospfAreaData for ospfAreaData in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfAreaData_subString in ospfAreaData]
            ospfRedist_subString = 'redistribute'
            ospfRedist_memberString = [ospfRedist for ospfRedist in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfRedist_subString in ospfRedist]
            ospfAutoCost_subString = 'auto-cost'
            ospfAutoCost_memberString = [ospfAutoCost for ospfAutoCost in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfAutoCost_subString in ospfAutoCost]
            ospfPassiveIf_subString = 'passive-interface default'
            ospfPassiveIf_memberString = [ospfPassiveIf for ospfPassiveIf in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfPassiveIf_subString in ospfPassiveIf]   
            ospfDefault_subString = 'default-information originate'
            ospfDefault_memberString = [ospfDefault for ospfDefault in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfDefault_subString in ospfDefault]     
            ospfDefaultAlways_subString = 'default-information originate always'
            ospfDefaultAlways_memberString = [ospfDefaultAlways for ospfDefaultAlways in ospf_tmpAttr_dict['vrf'][ospfVrf_key] if ospfDefaultAlways_subString in ospfDefaultAlways]  
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId] = {}
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['vrf'] = ospfVrf_key
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['log_adjacency_changes_detail'] = bool(True)
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['maximum_paths'] = 4
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']= {}
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['spf_delay'] = {}
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['spf_delay']['initial'] = 20
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['spf_delay']['min'] = 200
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['spf_delay']['max'] = 5000
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['lsa'] = {}
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['lsa']['rx_min_interval'] = 80
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['lsa']['tx_delay'] = {}
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['lsa']['tx_delay']['initial'] = 10 
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['lsa']['tx_delay']['min'] = 100 
            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['timers']['lsa']['tx_delay']['max'] = 5000
            if ospfRouterId_memberString:
                ospfRouterId = re.findall(r'\s+router-id\s(\S+)', ospfRouterId_memberString[0])
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['router_id'] = ospfRouterId[0]
            #if ospfAreaData_memberStrings:
            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'] = {}
            #    for ospfAreaData_memberString in ospfAreaData_memberStrings:
            #        ospfArea_dataId = re.findall(r'\s+area\s(\S+)', ospfAreaData_memberString)
            #        if ospfArea_dataId[0] not in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas']:
            #            parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]= {}
            #            #if 'nssa' in ospfAreaData_memberString and 'nssa' not in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]:
            #            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['type'] = 'nssa'
            #            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['no_summary'] = bool(False)
            #            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['nssa_only'] = bool(True)
            #            #    #parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['default_information_originate'] = {}   
            #            #    if 'no-summary' in ospfAreaData_memberString:
            #            #        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['no_summary'] = bool(True)
            #            #    #if 'no-redistribution' in ospfAreaData_memberString:
            #            #    #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['nssa']['nssa_only'] = bool(False)
            #            #    if 'default-information-originate' in ospfAreaData_memberString:
            #            #        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['default_information_originate'] = {}
            #            if 'filter-list' in ospfAreaData_memberString and 'filter' not in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]:
            #                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['filter'] = {}
            #                ospfFilterList = re.findall(r'\s+area\s\S+\sfilter-list\s\S+\s(\S+)', ospfAreaData_memberString)
            #                ospfFilterDir = re.findall(r'\s+area\s\S+\sfilter-list\s\S+\s\S+\s(\w+)', ospfAreaData_memberString)
            #                if ospfFilterDir[0] == 'in':
            #                    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['filter']['prefix_list'] = ospfFilterList[0]
            #        elif ospfArea_dataId[0] in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas']:
            #            #if 'nssa' in ospfAreaData_memberString and 'nssa' not in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]:
            #            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['type'] = 'nssa'
            #            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['no_summary'] = bool(False)
            #            #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['nssa_only'] = bool(True)
            #            #    if 'no-summary' in ospfAreaData_memberString:
            #            #        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['no_summary'] = bool(True)
            #            #    #if 'no-redistribution' in ospfAreaData_memberString:
            #            #    #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['nssa']['nssa_only'] = bool(False)
            #            #    if 'default-information-originate' in ospfAreaData_memberString:
            #            #        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['default_information_originate'] = {}
            #            #elif 'nssa' in ospfAreaData_memberString and 'nssa' in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]:
            #            #    if 'no-summary' in ospfAreaData_memberString:
            #            #        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['no_summary'] = bool(True)
            #            #    #if 'no-redistribution' in ospfAreaData_memberString:
            #            #    #    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['nssa_only'] = bool(False)
            #            #    if 'default-information-originate' in ospfAreaData_memberString:
            #            #        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['default_information_originate'] = {}
            #            if 'filter-list' in ospfAreaData_memberString and 'filter' not in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]:
            #                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['filter'] = {}
            #                ospfFilterList = re.findall(r'\s+area\s\S+\sfilter-list\s\S+\s(\S+)', ospfAreaData_memberString)
            #                ospfFilterDir = re.findall(r'\s+area\s\S+\sfilter-list\s\S+\s\S+\s(\w+)', ospfAreaData_memberString)
            #                if ospfFilterDir[0] == 'in':
            #                    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['filter']['prefix_list'] = ospfFilterList[0]
            #            elif 'filter-list' in ospfAreaData_memberString and 'filter' in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]:
            #                ospfFilterList = re.findall(r'\s+area\s\S+\sfilter-list\s\S+\s(\S+)', ospfAreaData_memberString)
            #                ospfFilterDir = re.findall(r'\s+area\s\S+\sfilter-list\s\S+\s\S+\s(\w+)', ospfAreaData_memberString)
            #                if ospfFilterDir[0] == 'in':
            #                    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['areas'][ospfArea_dataId[0]]['filter']['prefix_list'] = ospfFilterList[0]
            if ospfRedist_memberString:
                ospfRedist_type = re.findall(r'\s+redistribute\s(\w+)', ospfRedist_memberString[0])
                ospfRouteMap = re.findall(r'\s+redistribute\s\w+\sroute-map\s(\S+)', ospfRedist_memberString[0])
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['redistribute'] = {}
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['redistribute'][ospfRedist_type[0]] = {}
                if ospfRouteMap:
                    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['redistribute'][ospfRedist_type[0]]['route_map'] = ospfRouteMap[0] 
            if ospfAutoCost_memberString:
                osfpAutoCost = re.findall(r'\s+auto-cost\sreference-bandwidth\s(.+)', ospfAutoCost_memberString[0]) 
                if osfpAutoCost[0] == '100 Gbps':
                    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['auto_cost_reference_bandwidth'] = 100000
                else:
                    parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['auto_cost_reference_bandwidth'] = osfpAutoCost[0]
            if ospfPassiveIf_memberString:
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['passive_interface_default'] = bool(True)
            if ospfDefault_memberString:
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['default_information_originate'] = {}
            if ospfDefaultAlways_memberString:
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['default_information_originate'] = {}
                parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospf_processId]['default_information_originate']['always'] = bool(True)
       
        ### ADD BGP REDISTRIBUTION TO OSPF FOR CORE ADVERTISEMENTS ###
        if '-dis' in host or '-cn' in host:
            vrf_list = []
            for vrfId in parsed_stage_dict['tenants']['acmegrp']['vrfs']:
                if 'l3_interfaces' in parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrfId]:
                    vrf_list.append(vrfId)
            for ospfProcessId in parsed_stage_dict['cs_conf_router_ospf']['process_ids']:
                if parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]['vrf'] in vrf_list:
                    if 'redistribute' in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]:
                        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]['redistribute']['bgp'] = {}
                        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]['redistribute']['bgp']['route_map'] = 'BGP-TO-OSPF'
                    elif 'redistribute' not in parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]:
                        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]['redistribute'] = {}
                        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]['redistribute']['bgp'] = {}
                        parsed_stage_dict['cs_conf_router_ospf']['process_ids'][ospfProcessId]['redistribute']['bgp']['route_map'] = 'BGP-TO-OSPF'

        ### EDIT VRF VNIS ###
        vrf_vni_list = vrf_vnis()
        for vrf_vni in vrf_vni_list:
            if dcId == vrf_vni['dc']:
                if vrf_vni['vrf'] in parsed_stage_dict['tenants']['acmegrp']['vrfs']:
                    parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_vni['vrf']]['vrf_vni'] = int(vrf_vni['vrf_vni'])
                    parsed_stage_dict['tenants']['acmegrp']['vrfs'][vrf_vni['vrf']]['mlag_ibgp_peering_vlan'] =  int(vrf_vni['vrf_vni']) - 400

        """ Parse Port Channels """
        ### ONLY SEARCH FOR PORT CHANNELS IN AGG SWITCHES AS DIS/CN SWITCHES ARE HOSTLESS ###
        if '-agg' in host:
            confParsed_portChannels = confParse_file.find_objects(r'^interface port-channel') 
            portChannel_attr_dict = {}
            ifs_stage_dict['port_channel_interfaces'] = {}
            for confParsed_portChannels_obj in confParsed_portChannels:
                portChannel_id = (str(confParsed_portChannels_obj.text)).replace('interface ', '')
                portChannel_attr_dict[portChannel_id] = []
                ifs_stage_dict['port_channel_interfaces'][portChannel_id] = {}
                for portChannelCh_obj in confParsed_portChannels_obj.children:
                    portChannel_attr_dict[portChannel_id].append(str(portChannelCh_obj.text))
            for portChannel in portChannel_attr_dict:
                pcDescription_string = 'description'
                pcDescription_memberString = [pcDesc for pcDesc in portChannel_attr_dict[portChannel] if pcDescription_string in pcDesc]
                portCtype_string = 'switchport mode'
                portCtype_memberString = [portCtype for portCtype in portChannel_attr_dict[portChannel] if portCtype_string in portCtype]
                portCvlanNative_string = 'switchport trunk native'
                portCvlanNative_memberString = [portCvlanNative for portCvlanNative in portChannel_attr_dict[portChannel] if portCvlanNative_string in  portCvlanNative]
                portCtrunkAllowed_string = 'switchport trunk allowed vlan'
                portCtrunkAllowed_memberString = [portCtrunkAllowed for portCtrunkAllowed in portChannel_attr_dict[portChannel] if portCtrunkAllowed_string in  portCtrunkAllowed]
                portCpVlanNative_string = 'switchport private-vlan trunk native'
                portCpVlanNative_memberString = [portCpVlanNative for portCpVlanNative in portChannel_attr_dict[portChannel] if portCpVlanNative_string in  portCpVlanNative]
                portCtrunk_pVlanAllowed_string = 'switchport private-vlan trunk allowed vlan'
                portCtrunk_pVlanAllowed_memberString = [portCtrunk_pVlanAllowed for portCtrunk_pVlanAllowed in portChannel_attr_dict[portChannel] if portCtrunk_pVlanAllowed_string in  portCtrunk_pVlanAllowed]
                portCpVlanMap_string = 'switchport private-vlan mapping trunk'
                portCpVlanMap_memberStrings = [portCpVlanMap for portCpVlanMap in portChannel_attr_dict[portChannel] if portCpVlanMap_string in  portCpVlanMap]
                portCpVlanAsoc_string = 'switchport private-vlan association'
                portCpVlanAsoc_memberStrings = [portCpVlanAsoc for portCpVlanAsoc in portChannel_attr_dict[portChannel] if portCpVlanAsoc_string in  portCpVlanAsoc]
                portCpVlanAsocHost_string = 'switchport private-vlan host-association'
                portCpVlanAsocHost_memberStrings = [portCpVlanAsocHost for portCpVlanAsocHost in portChannel_attr_dict[portChannel] if portCpVlanAsocHost_string in portCpVlanAsocHost ]
                portCvpcId_string = 'vpc'
                portCvpcId_memberString = [portCvpcId for portCvpcId in portChannel_attr_dict[portChannel] if portCvpcId_string in portCvpcId]
                portCstormC_string = 'storm-control'
                portCstormC_memberStrings = [portCstormC for portCstormC in portChannel_attr_dict[portChannel] if portCstormC_string in portCstormC]
                portCstpEdge_string = 'spanning-tree port type edge'
                portCstpEdge_memberString = [portCstp for portCstp in portChannel_attr_dict[portChannel] if portCstpEdge_string in portCstp]
                portCstp_attr_string = 'spanning-tree'
                portCstp_attr_memberStrings = [portCstp_attr for portCstp_attr in portChannel_attr_dict[portChannel] if portCstp_attr_string in portCstp_attr]
                portClacpSusp_string = 'no lacp suspend-individual'
                portClacpSusp_memberString = [portClacpSusp for portClacpSusp in portChannel_attr_dict[portChannel] if portClacpSusp_string in portClacpSusp]
                portCspeed_string = 'speed'
                portCspeed_memberString = [portCspeed for portCspeed in portChannel_attr_dict[portChannel] if portCspeed_string in portCspeed]
                if pcDescription_memberString: 
                    pcDescription = re.findall(r'\s+description\s(\S+).*', pcDescription_memberString[0])
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['description'] = pcDescription[0] 
                if portCtype_memberString:
                    portCtype = re.findall(r'\s+switchport\smode\s(.*)', portCtype_memberString[0] )
                    if portCtype[0] == 'private-vlan trunk secondary':
                        ifs_stage_dict['port_channel_interfaces'][portChannel]['mode'] = 'trunk'
                        ifs_stage_dict['port_channel_interfaces'][portChannel]['trunk_private_vlan_secondary'] = bool(True)
                        if portCpVlanNative_memberString:
                            portCpVlanNative = re.findall(r'\s+switchport\sprivate-vlan\strunk\snative\svlan\s(.*)', portCpVlanNative_memberString[0])
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['native_vlan'] = portCpVlanNative[0]
                        if portCtrunk_pVlanAllowed_memberString:
                            portCtrunk_pVlanAllowed  = re.findall(r'\s+switchport\sprivate-vlan\strunk\sallowed\svlan\s(.*)', portCtrunk_pVlanAllowed_memberString[0])
                            portCtrunk_pVlanAllowed_list = portCtrunk_pVlanAllowed[0].split(',')
                            if portCpVlanAsoc_memberStrings:
                                    portCsecondaryPvlan_list = []
                                    for portCpVlanAsoc_memberString in portCpVlanAsoc_memberStrings:
                                        portCpVlanAsoc = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s(.*)', portCpVlanAsoc_memberString)
                                        portCsecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s\d+\s(.*)', portCpVlanAsoc_memberString)
                                        portCsecondaryPvlan_list.append(portCsecondaryPvlan[0])
                                        portCpVlanAsoc_elements = portCpVlanAsoc[0].split(' ')
                                        for portCpVlanAsoc_element in portCpVlanAsoc_elements:
                                            portCtrunk_pVlanAllowed_list.append(portCpVlanAsoc_element)
                                    portCtrunk_pVlanAllowed_listString = ','
                                    ifs_stage_dict['port_channel_interfaces'][portChannel]['vlans'] = portCtrunk_pVlanAllowed_listString.join(portCtrunk_pVlanAllowed_list)
                                    portCsecondaryPvlan_string = ','
                                    ifs_stage_dict['port_channel_interfaces'][portChannel]['pvlan_mapping'] = portCsecondaryPvlan_string.join(portCsecondaryPvlan_list)
                        else:
                            if portCpVlanAsoc_memberStrings:
                                    portCsecondaryPvlan_list = []
                                    for portCpVlanAsoc_memberString in portCpVlanAsoc_memberStrings:
                                        portCpVlanAsoc = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s(.*)', portCpVlanAsoc_memberString)
                                        portCsecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s\d+\s(.*)', portCpVlanAsoc_memberString)
                                        portCsecondaryPvlan_list.append(portCsecondaryPvlan[0])
                                    portCsecondaryPvlan_string = ','
                                    ifs_stage_dict['port_channel_interfaces'][portChannel]['pvlan_mapping'] = portCsecondaryPvlan_string.join(portCsecondaryPvlan_list)
                    elif portCtype[0] == 'private-vlan trunk promiscuous':
                        ifs_stage_dict['port_channel_interfaces'][portChannel]['mode'] = 'trunk'                  
                        if portCpVlanNative_memberString:
                            portCpVlanNative = re.findall(r'\s+switchport\sprivate-vlan\strunk\snative\svlan\s(.*)', portCpVlanNative_memberString[0])
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['native_vlan'] = portCpVlanNative[0]
                        if portCtrunk_pVlanAllowed_memberString:
                            portCtrunk_pVlanAllowed  = re.findall(r'\s+switchport\sprivate-vlan\strunk\sallowed\svlan\s(.*)', portCtrunk_pVlanAllowed_memberString[0])
                            portCtrunk_pVlanAllowed_list = portCtrunk_pVlanAllowed[0].split(',')
                            if portCpVlanMap_memberStrings:
                                portCsecondaryPvlan_list = []
                                ifs_stage_dict['port_channel_interfaces'][portChannel]['vlan_translations'] = []
                                for portCpVlanMap_memberString in portCpVlanMap_memberStrings:
                                    portCtranslation_tmpDict = {}
                                    portCpVlanMap = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s(.*)', portCpVlanMap_memberString)
                                    portCsecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s\d+\s(.*)', portCpVlanMap_memberString)
                                    portCprimaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s(\d+)', portCpVlanMap_memberString)
                                    portCsecondaryPvlan_list.append(portCsecondaryPvlan[0])
                                    portCpVlanMap_elements = portCpVlanMap[0].split(' ')
                                    portCtranslation_tmpDict['from'] = portCsecondaryPvlan[0]
                                    portCtranslation_tmpDict['to'] = portCprimaryPvlan[0]
                                    portCtranslation_tmpDict['direction'] = 'out'
                                    ifs_stage_dict['port_channel_interfaces'][portChannel]['vlan_translations'].append(portCtranslation_tmpDict)
                                    for portCpVlanMap_element in portCpVlanMap_elements:
                                        portCtrunk_pVlanAllowed_list.append(portCpVlanMap_element)
                                portCtrunk_pVlanAllowed_listString = ','
                                ifs_stage_dict['port_channel_interfaces'][portChannel]['vlans'] = portCtrunk_pVlanAllowed_listString.join(portCtrunk_pVlanAllowed_list)
                                portCsecondaryPvlan_string = ','
                                ifs_stage_dict['port_channel_interfaces'][portChannel]['pvlan_mapping'] = portCsecondaryPvlan_string.join(portCsecondaryPvlan_list)
                        else:
                            if portCpVlanMap_memberStrings:
                                portCsecondaryPvlan_list = []
                                ifs_stage_dict['port_channel_interfaces'][portChannel]['vlan_translations'] = []
                                for portCpVlanMap_memberString in portCpVlanMap_memberStrings:
                                    portCtranslation_tmpDict = {}
                                    portCsecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s\d+\s(.*)', portCpVlanMap_memberString)
                                    portCprimaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s(\d+)', portCpVlanMap_memberString)
                                    portCsecondaryPvlan_list.append(portCsecondaryPvlan[0])
                                    portCtranslation_tmpDict['from'] = portCsecondaryPvlan[0]
                                    portCtranslation_tmpDict['to'] = portCprimaryPvlan[0]
                                    portCtranslation_tmpDict['direction'] = 'out'
                                    ifs_stage_dict['port_channel_interfaces'][portChannel]['vlan_translations'].append(portCtranslation_tmpDict)
                                portCsecondaryPvlan_string = ','
                                ifs_stage_dict['port_channel_interfaces'][portChannel]['pvlan_mapping'] = portCsecondaryPvlan_string.join(portCsecondaryPvlan_list)
                    else:
                        ifs_stage_dict['port_channel_interfaces'][portChannel]['mode'] = portCtype[0]
                        if portCvlanNative_memberString:
                            portCvlanNative = re.findall(r'\s+switchport\strunk\snative\svlan\s(.*)', portCvlanNative_memberString[0])
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['native_vlan'] = portCvlanNative[0]
                        if portCtrunkAllowed_memberString:
                            portCtrunkAllowed = re.findall(r'\s+switchport\strunk\sallowed\svlan\s(.*)',portCtrunkAllowed_memberString[0])
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['vlans'] = portCtrunkAllowed[0]   
                if portCpVlanAsocHost_memberStrings:
                    portCpVlanAsocHost = re.findall(r'\s+switchport\sprivate-vlan\shost-association\s\d+\s(.*)', portCpVlanAsocHost_memberStrings[0])
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['mode'] = 'access'
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['vlans'] = portCpVlanAsocHost[0]
                if portCvpcId_memberString:
                    portCvpcId = re.findall(r'\svpc\s(.*)',portCvpcId_memberString[0])
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['mlag'] = portCvpcId[0]
                if portCstormC_memberStrings:
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control'] = {}
                    for portCstormC_memberString in portCstormC_memberStrings:
                        portCstormBcPrct = re.findall(r'\s+storm-control\sbroadcast\slevel\s(\d+\.\d+)', portCstormC_memberString)
                        portCstormBcPps = re.findall(r'\s+storm-control\sbroadcast\slevel\spps\s(\d+)', portCstormC_memberString)
                        portCstormMcPrct = re.findall(r'\s+storm-control\smulticast\slevel\s(\d+\.\d+)', portCstormC_memberString)
                        portCstormMcPps = re.findall(r'\s+storm-control\smulticast\slevel\spps\s(\d+)', portCstormC_memberString)
                        portCstormUcPrct = re.findall(r'\s+storm-control\sunicast\slevel\s(\d+\.\d+)', portCstormC_memberString)
                        portCstormUcPps = re.findall(r'\s+storm-control\sunicast\slevel\spps\s(\d+)', portCstormC_memberString)
                        if portCstormBcPrct:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['broadcast'] = {}
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['broadcast']['level'] = portCstormBcPrct[0]
                        if portCstormBcPps:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['broadcast'] = {}
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['broadcast']['level'] = portCstormBcPps[0]
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['broadcast']['unit'] = 'pps' 
                        if portCstormMcPrct:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['multicast'] = {}
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['multicast']['level'] = portCstormMcPrct[0]
                        if portCstormMcPps:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['multicast'] = {}
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['multicast']['level'] = portCstormMcPps[0]
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['multicast']['unit'] = 'pps' 
                        if portCstormUcPrct:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['unknown_unicast'] = {}
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['unknown_unicast']['level'] = portCstormUcPrct[0]
                        if portCstormUcPps:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['unknown_unicast'] = {}
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['unknown_unicast']['level'] = portCstormUcPps[0]
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['storm_control']['unknown_unicast']['unit'] = 'pps' 
                if portCstpEdge_memberString:
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['spanning_tree_portfast'] = 'edge'
                if portCstp_attr_memberStrings:
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['stp_properties'] = []
                    for portCstp_attr_memberString in portCstp_attr_memberStrings:
                        portCstp_attr = re.findall(r'\s+spanning-tree\s(.*)',portCstp_attr_memberString)
                        if 'port type' not in portCstp_attr[0]:
                            ifs_stage_dict['port_channel_interfaces'][portChannel]['stp_properties'].append(portCstp_attr[0])
                if portClacpSusp_memberString:
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['lacp_fallback_mode'] = 'individual'
                if portCspeed_memberString:
                    portCspeed = re.findall(r'\s+speed\s(.*)', portCspeed_memberString[0])
                    ifs_stage_dict['port_channel_interfaces'][portChannel]['speed'] = portCspeed[0]
                ### REMOVE FEX PORT CHANNELS ###
                if portCtype[0] == 'fabricpath' or portCtype[0] == 'fex-fabric':
                    ifs_stage_dict['port_channel_interfaces'].pop(portChannel, None)
            ### REMOVE UNUSED/DOWN PORT CHANNELS ###
            for unusedIf in unusedIfs_list:
                if unusedIf in ifs_stage_dict['port_channel_interfaces']: 
                    ifs_stage_dict['port_channel_interfaces'].pop(unusedIf, None)    

        """ Parse Ethernet Interfaces """
        ### ONLY SEARCH FOR SINGLE HOST INTERFACES IN AGG SWITCHES AS DIS/CN SWITCHES ARE HOSTLESS ###
        if '-agg' in host:
            confParsed_ifs = confParse_file.find_objects(r'^interface Ethernet') 
            if_attr_dict = {}
            ifs_stage_dict['ethernet_interfaces'] = {}
            for confParsed_ifs_obj in confParsed_ifs:
                if_id = (str(confParsed_ifs_obj.text)).replace('interface ', '')
                if_attr_dict[if_id] = []
                for ifCh_obj in confParsed_ifs_obj.children:
                    if_attr_dict[if_id].append(str(ifCh_obj.text))
            for interface in if_attr_dict:
                ifPortC_string = 'channel-group'
                ifPortC_memberString = [ifPortC for ifPortC in if_attr_dict[interface] if ifPortC_string in ifPortC]
                ifState_string = 'shutdown'
                ifState_memberString = [ifState for ifState in if_attr_dict[interface] if ifState_string in ifState]
                ### DO NOT ADD INTERFACES ASSOCIATED TO A PORT CHANNEL ###
                if ifPortC_memberString or ifState_memberString:
                    pass
                elif not ifPortC_memberString or not ifState_memberString:
                    ifName = re.findall(r'(Ethernet\d/\d+$|Ethernet\d/\d+/\d$)', interface)
                    if ifName:
                        ifs_stage_dict['ethernet_interfaces'][ifName[0]] = {}
                        ifDescription_string = 'description'
                        ifDescription_memberString = [ifDesc for ifDesc in if_attr_dict[ifName[0]] if ifDescription_string in ifDesc]
                        ifType_string = 'switchport mode'
                        ifType_memberString = [ifType for ifType in if_attr_dict[ifName[0]] if ifType_string in ifType]
                        ifVlanNative_string = 'switchport trunk native'
                        ifVlanNative_memberString = [ifVlanNative for ifVlanNative in if_attr_dict[ifName[0]] if ifVlanNative_string in ifVlanNative]
                        ifTrunkAllowed_string = 'switchport trunk allowed vlan'
                        ifTrunkAllowed_memberString = [ifTrunkAllowed for ifTrunkAllowed in if_attr_dict[ifName[0]] if ifTrunkAllowed_string in ifTrunkAllowed]
                        ifPvlanNative_string = 'switchport private-vlan trunk native'
                        ifPvlanNative_memberString = [ifPvlanNative for ifPvlanNative in if_attr_dict[ifName[0]] if ifPvlanNative_string in ifPvlanNative]
                        ifTrunk_pVlanAllowed_string = 'switchport private-vlan trunk allowed vlan'
                        ifTrunk_pVlanAllowed_memberString = [ifTrunk_pVlanAllowed for ifTrunk_pVlanAllowed in if_attr_dict[ifName[0]] if ifTrunk_pVlanAllowed_string in ifTrunk_pVlanAllowed]
                        ifPvlanMap_string = 'switchport private-vlan mapping trunk'
                        ifPvlanMap_memberStrings = [ifPvlanMap for ifPvlanMap in if_attr_dict[ifName[0]] if ifPvlanMap_string in ifPvlanMap]
                        ifPvlanAsoc_string = 'switchport private-vlan association'
                        ifPvlanAsoc_memberStrings = [ifPvlanAsoc for ifPvlanAsoc in if_attr_dict[ifName[0]] if ifPvlanAsoc_string in ifPvlanAsoc ]
                        ifPvlanAsocHost_string = 'switchport private-vlan host-association'
                        ifPvlanAsocHost_memberStrings = [ifPvlanAsocHost for ifPvlanAsocHost in if_attr_dict[ifName[0]] if ifPvlanAsocHost_string in ifPvlanAsocHost ]
                        ifMonitor_string = 'switchport monitor'
                        ifMonitor_memberString = [ifMonitor for ifMonitor in if_attr_dict[ifName[0]] if ifMonitor_string in ifMonitor]
                        ifStormC_string = 'storm-control'
                        ifStormC_memberStrings = [ifStormBc for ifStormBc in if_attr_dict[ifName[0]] if ifStormC_string in ifStormBc]
                        ifStpEdge_string = 'spanning-tree port type edge'
                        ifStpEdge_memberString = [ifStp for ifStp in if_attr_dict[ifName[0]] if ifStpEdge_string in ifStp]
                        if ifDescription_memberString: 
                            ifDescription = re.findall(r'\s+description\s(\S+).*', ifDescription_memberString[0])
                            ifs_stage_dict['ethernet_interfaces'][ifName[0]]['description'] = ifDescription[0]
                        if ifType_memberString:
                            ifType = re.findall(r'\s+switchport\smode\s(.*)', ifType_memberString[0])
                            if ifType[0] == 'private-vlan trunk secondary':
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['mode'] = 'trunk'
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['trunk_private_vlan_secondary'] = bool(True)
                                if ifPvlanNative_memberString:
                                    ifPvlanNative = re.findall(r'\s+switchport\sprivate-vlan\strunk\snative\svlan\s(.*)', ifPvlanNative_memberString[0])
                                    ifs_stage_dict['ethernet_interfaces'][ifName[0]]['native_vlan'] = ifPvlanNative[0]
                                if ifTrunk_pVlanAllowed_memberString:
                                    ifTrunk_pVlanAllowed  = re.findall(r'\s+switchport\sprivate-vlan\strunk\sallowed\svlan\s(.*)', ifTrunk_pVlanAllowed_memberString[0])
                                    ifTrunk_pVlanAllowed_list = ifTrunk_pVlanAllowed[0].split(',')
                                    if ifPvlanAsoc_memberStrings:
                                            ifSecondaryPvlan_list = []
                                            for ifPvlanAsoc_memberString in ifPvlanAsoc_memberStrings:
                                                ifPvlanAsoc = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s(.*)', ifPvlanAsoc_memberString)
                                                ifSecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s\d+\s(.*)', ifPvlanAsoc_memberString)
                                                ifSecondaryPvlan_list.append(ifSecondaryPvlan[0])
                                                ifPvlanAsoc_elements = portCpVlanAsoc[0].split(' ')
                                                for ifPvlanAsoc_element in ifPvlanAsoc_elements:
                                                    ifTrunk_pVlanAllowed_list.append(ifPvlanAsoc_element)
                                            ifTrunk_pVlanAllowed_listString = ','
                                            ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlans'] = ifTrunk_pVlanAllowed_listString.join(ifTrunk_pVlanAllowed_list)
                                            ifSecondaryPvlan_string = ','
                                            ifs_stage_dict['ethernet_interfaces'][ifName[0]]['pvlan_mapping'] = ifSecondaryPvlan_string.join(ifSecondaryPvlan_list)
                                else:
                                    if ifPvlanAsoc_memberStrings:
                                            ifSecondaryPvlan_list = []
                                            for ifPvlanAsoc_memberString in ifPvlanAsoc_memberStrings:
                                                ifpVlanAsoc = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s(.*)', ifPvlanAsoc_memberString)
                                                ifSecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s\d+\s(.*)', ifPvlanAsoc_memberString)
                                                ifSecondaryPvlan_list.append(ifSecondaryPvlan[0])
                                            ifSecondaryPvlan_string = ','
                                            ifs_stage_dict['ethernet_interfaces'][ifName[0]]['pvlan_mapping'] = ifSecondaryPvlan_string.join(ifSecondaryPvlan_list)
                            elif ifType[0] == 'private-vlan trunk promiscuous':
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['mode'] = 'trunk'                  
                                if ifPvlanNative_memberString:
                                    ifPvlanNative = re.findall(r'\s+switchport\sprivate-vlan\strunk\snative\svlan\s(.*)', ifPvlanNative_memberString[0])
                                    ifs_stage_dict['ethernet_interfaces'][ifName[0]]['native_vlan'] = ifPvlanNative[0]
                                if ifTrunk_pVlanAllowed_memberString:
                                    ifTrunk_pVlanAllowed  = re.findall(r'\s+switchport\sprivate-vlan\strunk\sallowed\svlan\s(.*)', ifTrunk_pVlanAllowed_memberString[0])
                                    ifTrunk_pVlanAllowed_list = ifTrunk_pVlanAllowed[0].split(',')
                                    if ifPvlanMap_memberStrings:
                                        ifSecondaryPvlan_list = []
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlan_translations'] = []
                                        for ifPvlanMap_memberString in ifPvlanMap_memberStrings:
                                            ifTranslation_tmpDict = {}
                                            ifPvlanMap = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s(.*)', ifPvlanMap_memberString)
                                            ifSecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s\d+\s(.*)', ifPvlanMap_memberString)
                                            ifPrimaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s(\d+)', ifPvlanMap_memberString)
                                            ifSecondaryPvlan_list.append(ifSecondaryPvlan[0])
                                            ifPvlanMap_elements = ifPvlanMap[0].split(' ')
                                            ifTranslation_tmpDict['from'] = ifSecondaryPvlan[0]
                                            ifTranslation_tmpDict['to'] = ifPrimaryPvlan[0]
                                            ifTranslation_tmpDict['direction'] = 'out'
                                            ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlan_translations'].append(ifTranslation_tmpDict)
                                            for ifPvlanMap_element in ifPvlanMap_elements:
                                                ifTrunk_pVlanAllowed_list.append(ifPvlanMap_element)
                                        ifTrunk_pVlanAllowed_listString = ','
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlans'] = ifTrunk_pVlanAllowed_listString.join(ifTrunk_pVlanAllowed_list)
                                        ifSecondaryPvlan_string = ','
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['pvlan_mapping'] = ifSecondaryPvlan_string.join(ifSecondaryPvlan_list)
                                else:
                                    if ifPvlanMap_memberStrings:
                                        ifSecondaryPvlan_list = []
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlan_translations'] = []
                                        for ifPvlanMap_memberString in ifPvlanMap_memberStrings:
                                            ifTranslation_tmpDict = {}
                                            ifSecondaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s\d+\s(.*)', ifPvlanMap_memberString)
                                            ifPrimaryPvlan = re.findall(r'\s+switchport\sprivate-vlan\smapping\strunk\s(\d+)', ifPvlanMap_memberString)
                                            ifSecondaryPvlan_list.append(ifSecondaryPvlan[0])
                                            ifTranslation_tmpDict['from'] = ifSecondaryPvlan[0]
                                            ifTranslation_tmpDict['to'] = ifPrimaryPvlan[0]
                                            ifTranslation_tmpDict['direction'] = 'out'
                                            ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlan_translations'].append(ifTranslation_tmpDict)
                                        ifSecondaryPvlan_string = ','
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['pvlan_mapping'] = ifSecondaryPvlan_string.join(ifSecondaryPvlan_list)
                            else:
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['mode'] = ifType[0]
                                if ifVlanNative_memberString:
                                    ifVlanNative = re.findall(r'\s+switchport\strunk\snative\svlan\s(.*)', ifVlanNative_memberString[0])
                                    ifs_stage_dict['ethernet_interfaces'][ifName[0]]['native_vlan'] = ifVlanNative[0]
                                if ifTrunkAllowed_memberString:
                                    ifTrunkAllowed = re.findall(r'\s+switchport\strunk\sallowed\svlan\s(.*)',ifTrunkAllowed_memberString[0])
                                    ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlans'] = ifTrunkAllowed[0]  
                            if ifMonitor_memberString:
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['switch_monitor'] = bool(True)
                            if ifStormC_memberStrings:
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control'] = {}
                                for ifStormC_memberString in ifStormC_memberStrings:
                                    ifStormBcPrct = re.findall(r'\s+storm-control\sbroadcast\slevel\s(\d+\.\d+)', ifStormC_memberString)
                                    ifStormBcPps = re.findall(r'\s+storm-control\sbroadcast\slevel\spps\s(\d+)', ifStormC_memberString)
                                    ifStormMcPrct = re.findall(r'\s+storm-control\smulticast\slevel\s(\d+\.\d+)', ifStormC_memberString)
                                    ifStormMcPps = re.findall(r'\s+storm-control\smulticast\slevel\spps\s(\d+)', ifStormC_memberString)
                                    ifStormUcPrct = re.findall(r'\s+storm-control\sunicast\slevel\s(\d+\.\d+)', ifStormC_memberString)
                                    ifStormUcPps = re.findall(r'\s+storm-control\sunicast\slevel\spps\s(\d+)', ifStormC_memberString)
                                    if ifStormBcPrct:
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['broadcast'] = {}
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['broadcast']['level'] = ifStormBcPrct[0]
                                    if ifStormBcPps:
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['broadcast'] = {}
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['broadcast']['level'] = ifStormBcPps[0]
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['broadcast']['unit'] = 'pps' 
                                    if ifStormMcPrct:
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['multicast'] = {}
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['multicast']['level'] = ifStormMcPrct[0]
                                    if ifStormMcPps:
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['multicast'] = {}
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['multicast']['level'] = ifStormMcPps[0]
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['multicast']['unit'] = 'pps' 
                                    if ifStormUcPrct:
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['unknown_unicast'] = {}
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['unknown_unicast']['level'] = ifStormUcPrct[0]
                                    if ifStormUcPps:
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['unknown_unicast'] = {}
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['unknown_unicast']['level'] = ifStormUcPps[0]
                                        ifs_stage_dict['ethernet_interfaces'][ifName[0]]['storm_control']['unknown_unicast']['unit'] = 'pps' 
                            if ifStpEdge_memberString:
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['spanning_tree_portfast'] = 'edge'
                            if ifPvlanAsoc_memberStrings:
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['private_vlan_associations'] = []
                                for ifPvlanAsoc_memberString in ifPvlanAsoc_memberStrings:
                                    ifPvlanAsoc = re.findall(r'\s+switchport\sprivate-vlan\sassociation\strunk\s(.*)', ifPvlanAsoc_memberString)
                                    ifs_stage_dict['ethernet_interfaces'][ifName[0]]['private_vlan_associations'].append(ifPvlanAsoc[0])
                            if ifPvlanAsocHost_memberStrings:
                                ifPvlanAsocHost = re.findall(r'\s+switchport\sprivate-vlan\shost-association\s\d+\s(.*)', ifPvlanAsocHost_memberStrings[0])
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['mode'] = 'access'
                                ifs_stage_dict['ethernet_interfaces'][ifName[0]]['vlans'] = ifPvlanAsocHost[0]
            ### REMOVE UNUSED/DOWN INTERFACES ###
            for unusedIf in unusedIfs_list:
                if unusedIf in ifs_stage_dict['ethernet_interfaces']: 
                    ifs_stage_dict['ethernet_interfaces'].pop(unusedIf, None)

        """ Create Staging YAML files for Group Vars"""    
        print( host +": Writing Data to YAML...")
        yaml_toFile(host, parsed_stage_dict)
        yaml_toFile(host, ifs_stage_dict, 'ifs_data/')
        """ Combine Campus and DCs YAML Files"""
    ### LOAD YAML DICTIONARIES ###
    
    dc01dis_dict = load_yamlFile(yaml_dir / 'swex-dc01-dis3.yml')
    dc02dis_dict = load_yamlFile(yaml_dir / 'swex-dc02-dis3.yml')
    campus7_dict = load_yamlFile(yaml_dir / 'swex-dc01-cn1.yml')
    campus8_dict = load_yamlFile(yaml_dir / 'swex-dc02-cn2.yml')
    dh01dis_dict = load_yamlFile(yaml_dir / 'swex-dh01-dis3.yml')
        
    ### COMBINE YAML FILES ###
    dc01_border = combine_yamlFiles(dc01dis_dict, campus7_dict)
    dc02_border = combine_yamlFiles(dc02dis_dict, campus8_dict)

    ### COMPARE VLANs ON BORDERS AND LEAVES ###
    dc01blVlan_list = []
    dc02blVlan_list = []
    dh01blVlan_list = []
    for vrfID in dc01_border['tenants']['acmegrp']['vrfs']:
        for sviId in  dc01_border['tenants']['acmegrp']['vrfs'][vrfID]['svis']:
            dc01blVlan_list.append(sviId)
    for l2Vlan in dc01_border['tenants']['acmegrp']['l2vlans']:
        dc01blVlan_list.append(l2Vlan)
    for vrfID in dc02_border['tenants']['acmegrp']['vrfs']:
        for sviId in  dc02_border['tenants']['acmegrp']['vrfs'][vrfID]['svis']:
            dc02blVlan_list.append(sviId)
    for l2Vlan in dc02_border['tenants']['acmegrp']['l2vlans']:
        dc02blVlan_list.append(l2Vlan)
    for vrfID in dh01dis_dict['tenants']['acmegrp']['vrfs']:
        for sviId in dh01dis_dict['tenants']['acmegrp']['vrfs'][vrfID]['svis']:
            dh01blVlan_list.append(sviId)
    for l2Vlan in dh01dis_dict['tenants']['acmegrp']['l2vlans']:
        dh01blVlan_list.append(l2Vlan)
    dc01vlan_cleanList = rm_listDup(dc01vlan_list)  
    dc02vlan_cleanList = rm_listDup(dc02vlan_list)
    dh01vlan_cleanList = rm_listDup(dh01vlan_list)  
    for dc01vlan in dc01vlan_cleanList:
        if dc01vlan not in dc01blVlan_list:
            print(dcId + ': Vlan inconsistency...')
            print(dc01vlan)
    for dc02vlan in dc02vlan_cleanList:
        if dc02vlan not in dc02blVlan_list:
            print(dcId + ': Vlan inconsistency...')
            print(dc02vlan)
    for dh01vlan in dh01vlan_cleanList:
        if dh01vlan not in dh01blVlan_list:
            print(dcId + ': Vlan inconsistency...')
            print(dh01vlan)
    
    """ Create Arista YAML files for Group Vars"""    
    print('dc01_border: Writing Data to YAML...')
    yaml_toFile('dc01_border', dc01_border)
    print('dc02_border: Writing Data to YAML...')
    yaml_toFile('dc02_border', dc02_border)
    print('dh01_border: Writing Data to YAML...')
    yaml_toFile('dh01_border', dh01dis_dict)

    """ Move Files to New Folder Location """
    print('Moving YAML Structured Files to the group_vars directory...')
    mv_yamlFiles(yaml_dir, fabric_dir)

    ''' Generate Leaf Files '''
    print('Generate Leaf Group Vars Files...')
    create_leafs_varsFile()
                       
if __name__ == '__main__':
    main()
