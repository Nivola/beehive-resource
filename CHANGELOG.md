# Changelog

## Version 1.14.0 (, 2023)

* Added ...


* Fixed ...
    * fix bug that caused sync of new discovered Openstack.Image objects to fail


* Integrated ...


## Version 1.13.0 (oct 21, 2022)

* Added ...
    * now compute instance support static ip passed from api
    * add new async functions patch2. Use in the place of patch
    * add new async functions expunge2. Use in the place of expunge
    * add view method expunge_resource2. Use in the place of expunge_resource
    * add zabbix host do_expunge method
    * add management of security group zabbix proxy ingress rule
    * add resource api v2 with management of async internal class methods
    * add dummy_v2 entities
    * add gitlab container
    * add host_group info in provider instance. Read from openstack and vsphere
    * add sql stack info fields attributes.backup_enabled, attributes.monitoring_enabled, attributes.logging_enabled
* Fixed ...
    * correct errors in pre_import for ComputeInstance
    * fixed problem with name propagation of ComputeLoggingSpace
    * fixed problem when create a share using manila. Now search of share type use the share type description 
      in the place of name
    * set vsphere flavor as sync
* Integrated ...
    * improved creation of vsphere server with automatic setting of proxy for ubuntu vm
    * update flavor openstack to set extra specs
* Various bugfixes

## Version 1.12.0 (feb 11, 2022)

* Added ...
    * add base method to manage physical backup for Compute Instance of type openstack
    * add import api for stack sql v2
    * add support for server console in openstack, vsphere and in provider instance
    * base structure of ElasticIp [start]
    * new metrics for instances describing operating system and hypervisor instead of previous metrics describing license
    * add share label management to get custom svm
    * add new resource container ontap_netapp
    * extend provider share with orchestrator type ontap
    * add ElkPlugin, ComputeLoggingSpaceAPI, ComputeLoggingRoleAPI, ComputeLoggingRoleMappingAPI
    * add compute volume set flavor action
    * add filter by instance in security group get api
* Fixed ...
    * correct bug in provider image update
    * add check on flavor in compute instance import
    * security group does not get correctly instance connected
    * removed grant check in ComputeShare. Ip grant can be used also for cifs share
    * correct bug in site_network_add_subnet_step. If an allocation_pool is not configured step fails
    * fixed ComputeInstance info (like monitoring) explain
    * fixed ComputeInstance flavor info. Now flavor map exactly physical flavor
    * fixed ComputeVolume flavor info. Now flavor map exactly physical flavor
    * correct bug in ComputeRule filter
    * fixed zabbute user in postgresql sql stack
    * fixed compute availability zone expunge when some applied customizations already exist 
    * fixed bug in ComputeInstance snapshot
* Integrated ...
    * integrated customization_spec_name params in vsphere server creation
    * add missing task declarations in awx, openstack, zabbix
* Various bugfixes

## Version 1.11.0 (jun 11, 2021)

* Added ...
    * add compute instance methods to add/delete/change password to internal user
    * add api for applied customization
    * add ComputeBastion class
    * add Awx container AdHocCommand to run simple command on hosts
    * add ComputeInstance run_ad_hoc_command to run command on a vm using awx
    * add new action in SqlComputeStackV2 to get_dbs and get_users
* Fixed ...
    * fixed gateway errors when is evaluated subnet to use with vpc interpod
    * add Compute SecurityGroup method to get_rules
    * add Compute SecurityGroup check of existing rule in pre_delete
    * fixed creation of ComputeInstance with public network. Now multi avz is set automatically to false
    * add Compute Share get_quotas
    * correct bug during openstack volume remove. State was forced to available
    * fixed bug in openstack server clone in different pod
* Integrated ...
    * integrated error propagation from awx job to applied customization
* Various bugfixes
    * correct step create_zone_instance_step return that block task
    * correct bug in dns recorda and recordcname that block add record when name overlap between different zones
    * correct bug in get_aggregated_resource_from_physical_resource. If physical resource is linked to more than one
      aggregated resource is necessary a parent filter to select the correct one.
    * correct bug to compute rule. Now only active availability zones are used during creation

## Version 1.10.0 (Feb 05, 2021)

* Added ...
    * add filter for hypervisor in compute instance api
    * add the concept of bastion host in compute zone
    * add new api ping (with sql check), capabilities and version to /v1.0/nrs
    * add create openstack server from existing volume in the same container or in another container
    * add create openstack volume from existing volume in the same container or in another container
    * add create compute instance from existing volume in the same container or in another container
    * add compute instance methods to manage internal user [beta]
* Fixed ...
    * fixed bug in discover and synchronize openstack volume. List was limited to 1000 items
    * fixed bug in get quotas for sql stack v2. Ram was calculated in MB.
    * update openstack volume client with volume_v3 that use cinder v3 api
    * improved response time of stack_v2 list api
    * improved response time of ssql_tack_v2 list api
    * fixed sql stack creation in private compute zone. Must be configured (for the moment manually) a bastion host
    * improved response time of compute_instance list api
    * apply patch in server_expunge_physical_step. When ext_id is not valid get_ports got error
    * correct check of manage status of a ComputeInstance during creation
* Integrated ...
    * integrated check method in volume, server, compute instance and compute volume
    * add link id in resource tree
* Various bugfixes
    * correct some bug in compute volume info
    * correct some bugs in openstack container to support stein version

## Version 1.9.0 (Oct 23, 2020)

* Added ...
    * add sql_stack_v2 with sql stack based on stack_v2
    * added change of security group in openstack server
    * added change of security group in vsphere server
    * added openstack server snapshot add/remove/revert
    * added vsphere server snapshot add/remove/revert
    * added provider instance snapshot add/remove/revert
    * added create and delete of openstack share based on share network and local share server
    * added create and delete of provider share based on share network and local share server
    * add resource entity api to clean cache
* Fixed ...
    * fixed creation of vsphere server. If a template has more then one disk it is not registered
* Integrated ...
    * integrated api to set check quotas and metrics for resource
* Various bugfixes
	* fixed error generating swagger specification


## Version 1.8.1 (Jul 14, 2020)

* Added ...
    * ComputeGateway attach/detach vpc
    * ComputeGateway set default internet ruote
    * ComputeGateway manage firewall rules
    * ComputeGateway manage nat rules
    * ComputeGateway manage credentials
* Fixed ...
    * removed check quotas. Leave check only on service component
    * improved compute zone get metrics reducing overhead and adding metrics cache
    * improved security group rules list from api
    * ComputeGateway crud
    * Create Virtual Machine on private network
    * ping method in Awx container and Zabbix container
    * correct api of Customization and AppliedCustomization
* Integrated ...
* Various bugfixes
    * Correct info and detail bug in openstack image
    * Correct delete of datastore from vsphere volume type. Used Link.expunge instead of Link.delete
    * Correct bug in get_paginated_entities that return wrong number of records
    * Correct bug in site orchestrator delete for type Awx and Zabbix

## Version 1.8.0 (Jun 21, 2020)

* Added ...
    * new task_v2 for all the package
    * add scheduled start e stop for compute instance
    * add vpc_v2 with private vpc management
    * add ComputeCustomization
    * add ComputeGateway
    * add stack_v2 with stack management make by provider container
* Fixed ...
    * porting of all code to python 3
* Integrated ...
* Various bugfixes
    * Correct various bugs

## Version 1.7.0 (Sep , 2019)

* Added ...
* Fixed ...
    * replacemetent of vsphere task with task_v2
* Integrated ...
* Various bugfixes
    * correct bug when deleting openstack server. A port remained hanging
    * correct bug that blocks deletion of virtual machine when dns zone was not found
    * correct bug in post api of site_network. dns_search param is not read
    * correct bug in stack resource list. Volume with volume attachment is showed two times
    * correct bug in site-network append platform network
    * correct bug in vsphere datastore synchronization
* Removed

## Version 1.6.0 (Sep 04, 2019)

* Added ...
    * added management of compute volume snapshots
    * added import ComputeShare
    * added import ComputeInstance
    * added import ComputeVolume
    * assign trilio_backup_role to admin user when create a new project
* Fixed ...
    * revisionata api /v1.0/nrs/provider/site_networks/<oid>/network [PUT] per appendere reti di tipo vsphere e openstack
    * corretto il controllo della chiave ssh negli app_stack e sql_stack. Se non si trova openstack_name negli attributes
      viene fornito un errore. Senza la chiave in openstack heat non è in grado di generare lo stack
    * changed delete task of openstack volume, openstack instance and openstack stack to remove all the snapshots of the
      volumes
    * revisione generale api site-network
    * revisione e semplificazione dei metodi get_resource e get_resources
* Integrated ...
* Various bugfixes
* Removed
    * method ResourceController.get_errors()
    * method ResourceController.get_parent_resource_index()

## Version 1.5.0 (May 24, 2019)

* Added ...
    * aggiunto openstack VolumeType
    * **OpenstackVolume**: revisione generale
    * **OpenstackImage**: aggiunta lista metadati
    * aggiunto vsphere VolumeType
    * aggiunto vsphere Volume
    * aggiunto **ComputeVolumeFlavor**
    * aggiunto **ComputeVolume**
    * aggiunto metodo patch per una **ComputeInstance**
    * aggiunte api di add e del volume ad una **ComputeInstance**
    * aggiunta api di modifica state di una **Resource**
    * aggiunto campo last_error nel model **Resource**. Utilizzo di questo campo per salvare l'ultimo errore
    * aggiunta api su slq_stack che restituisce la lista degli engine
    * aggiunto parametro host_group nei server per indicare il cluster di allocazione in vsphere
* Fixed ...
    * modificato metdodo container.get_resource. Adesso setta direttamente il parent container e imposta il parent solo
      se details è True
    * ottimizzate list e get di OpenstackServer, OpenstackVolume, OpenstackHeatStack
* Integrated ...
    * modificata creazione server openstack. Adesso la creazione dei volumi si può fare a partire a un'immagine,
      da un volume esistente o da un snapshot. I volumi supportano i volume type
    * modificata la creazione delle ComputeInstance per agganciare i ComputeVolume con type=openstack
* Various bugfixes

## Version 1.4.0 (February 27, 2019)

* Added ...
    * **ComputeImage**: aggiunta minima dimensione disco immagine e elenco di hypervisor per zona
    * Aggiunto container dns
* Fixed ...
    * **app stack**: rivista struttura generale
* Integrated ...
* Various bugfixes
    * corretti bug nella cancellazione dei security group
    * corretti bug nella creazione delle rule vsphere
    * corretto un bug nella cancellazione dei server openstack

## Version 1.3.0 (February 01, 2019)

* Added ...
* Fixed ...
* Integrated ...
    * **ComputeZone**: aggiunta assegnazione automatica del ruolo master del gruppo ssh di una ComputeZone
      managed allo user o group specificato nel campo facoltativo managed_by
    * **ComputeZone**: aggiunta api che restituisce le availability zones
    * **ComputeZone**: rivista creazione section vsphere nsx dfw e folder vsphere
    * **ComputeServer**: rivista creazione server vsphere
    * **ComputeRule**: rivista creazione rule vsphere nsx dfw
* Various bugfixes
    * corretto bug nell'action di set_quotas della compute zone

## Version 1.2.0 (January 13, 2019)

* Added ...
* Fixed ...
* Integrated ...
    * **resource job**: aggiunta registrazione del job sul container oltre che sulla risorsa
    * **compute security group**: ottimizzati i metodi di interrogazioni
    * **compute stack**: rivista struttura generale
    * **compute share**: rivista struttura generale
* Various bugfixes

## Version 1.1.0 (July 31, 2018)

* Added ...
* Fixed ...
* Integrated ...
    * inizio revisione job di creazione. Rivisto la crreazione dei job. Cambio di invocazione di job da altri job. Non
      avviene più invocando l’api ma direttamente invocando il job.
    * **openstack**: aggiunta gestione action (start, stop, reboot, add-volume, del-volume, set-flavor)
    * **compute instance**: aggiunta gestione action (start, stop, set-flavor)
* Various bugfixes

## Version 1.0.0 (July 31, 2018)

First production preview release.

## Version 0.1.0 (April 18, 2016)

First private preview release.