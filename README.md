# nxos_to_eos

The main goal of this repository is to convert data from running configurations into YAML format to use as 
group_vars for the Arista AVD.

The program to collect running configurations and interface status information relies on Nornir's framework which handles the sessions.

To populate Nornir's inventory file:
1. From a CSV file

    A csv example file has been added under the data/ folder, this is the required format.
    The script called "py_import_csv.py" can then be run to create the nornir inventory.
    This file would then be placed under "config/hosts" which would be used by Nornir.
    
2. Once Nornir's inventory file has been created, the "pygetRunConfig.py" script is used to fetch 
   the running configuration of the inventory (placed on the run_conf/) and also runs the 'show interface status' 
   command and puts it in json format under the json_data/ directory. 

3. The python script has been added to the playbooks where it will work along the AVD collection to build the structured configuration and cli configurations as a result. 
   The "py_avdParsing.py" script uses ciscoConfParse library to parse the running configuration
   and transforms them into YAML format which complies with the AVD structure. 
   All this data is placed under the yaml_data/ directory and then moved to the group_vars folder.

   If the json_data has not been formatted yet, add the argument 'format_json_data' when running the script. This is required to use the data using the same format as the one used in the running configuration. ONLY to exclude unused port channels and interfaces and SHOULD ONLY BE RUN ONCE right after the running configurations have been collected.

4. An additional directory called 'ifs_data' is added to collect all active single interfaces and port-channels for reference when performing migration of services. The data is ready for avd consumption. 

5. Finally a python script named "py_consolidateStruct" checks the most up to date repository containing the running configurations. If it finds any diference, it updates the structured config and pushes it to a new branch.
