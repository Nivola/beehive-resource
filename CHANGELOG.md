# Changelog

## Version 1.18.2 (2026-03-12)

Rilascio nuove funzionalità
* Aggiunto
  - Edb con TDE
  - Implemented `count_monitoring_enabled` to replace heavy object retrieval during Zabbix monitoring checks, significantly improving performance.
* Risolto
  - fix ComputeStack get_metrics
  - Remove dead code
  - Improve resource lookup, caching, and monitoring checks
  - Refactor resource and link retrieval to reduce redundant queries and imports, add local caching, and batch customization for better performance.
  - Replace monitoring count queries with an existence check and cache the Zabbix resource type ID to minimize database overhead.
  - Fix minor issues and typos, remove redundant code, and improve error handling.
  - Fixed dangerous mutable default arguments in multiple method signatures (e.g., `params={}` -> `params=None`).
  - Refactored string formatting to use f-strings throughout the models and controllers.
  - Updated logging statements to use lazy formatting where appropriate.
  - Renamed local variables (e.g., `type`, `id`) to avoid shadowing Python built-ins.
  - Removed deprecated methods (`get_runstate_DEPRECATED`) and commented-out code.
  - Improved exception handling with explicit chaining (`raise ... from exc`).
  - map[get_metrics:update data cpu/ram if it has changed]
  - dbaas performance issue

## Version 1.18.1 (2026-02-12)

Rilascio nuove funzionalità
* Aggiunto
  - map[chore:add missing license headers]
  - custom ComputeProviderResourceActionTask for ComputeInstance, ComputeStackV2 (avoid resource in error)
  - update requirements
* Risolto
  - Bug fixing NSX firewall rules optimization
  - simple_info add data_info
  - removed "aaa" comments
  - removed last_runstate, add sg

## Version 1.18.0 (2026-01-22)

Rilascio nuove funzionalità
* Aggiunto
  - public ip metrics
  - share_v2 NA metrics added
  - type hints
  - paas as stack v2 and his netrics
* Risolto
  - updated python version, labraries and dependencies
  - schema definitions
  - fix some default
  - improved error message when increse disk with a non valid size
  - Fix port variable registering haproxy in dbaas
  - awx_job_template removed non ansi characters from awx errors
  - fix vpc and compute zone filter for security group list api
* Rimosso
  - unused files
  - six direct usage

## Version 1.17.13 (2025-12-11)

Rilascio nuove funzionalità
* Aggiunto
  - STAAS v2 volume size in info now read from platform instaed from attributes

## Version 1.17.12 (2025-11-27)

Rilascio nuove funzionalità
* Aggiunto
  - staas_ontap_v2 goldencopy (compliance) management for shared volumes
  - Force value of staas compliance metric equal to that of the main volume
  - refactoring dbaas moving data in definitions
  - metrics_prefix for ComputeInstance, ComputeVolume
* Risolto
  - Deleted commented code
  - Fix vpc free ip for private
  - staas v2 enable/disable compliance bug fix

## Version 1.17.11 (2025-11-06)

Rilascio nuove funzionalità
* Aggiunto
  - added 19EE3 as oracle 19c
  - stack helper commons
  - hard poweroff when delete vm or db

## Version 1.17.10 (2025-10-09)

Rilascio nuove funzionalità
* Aggiunto
  - dbaas metric prefix as parameters at creation time,  dbaas metrics as parameter in definition
  - Manage "sys" superuser access in staas v2 export policy rules
  - mariadb on awx02
  - vpc ip avalability checks
* Risolto
  - site get_orchestrator_and_container
  - fix Manila avoid error in case turn off
  - fix import sqlserver

## Version 1.17.7 (2025-08-05)

Rilascio nuove funzionalità
* Aggiunto
  - SecurityGroup rule apply to NSX security group not to NSX distribuited firewall

## Version 1.17.6 (2025-06-10)

Rilascio nuove funzionalità
* Risolto
  - ComputeInstance now cache information and detail only if full initialized

## Version 1.17.5 ()

Rilascio nuove funzionalità
* Risolto
  - Ontap volumes get and show snapmirror policy
  - staas v2 snapmirror policy update
  - staas v2 multiple grants deletion
  - Remove clients from awx extra vars in staas v2 revoke grant

## Version 1.17.4 (2025-04-17)

Rilascio nuove funzionalità
* Risolto
  - map[openstack server, volume delete:add log]
  - backup faster load instances, load compute and stack instances, restore point stack, fix status job, fix Veeam restore point by job
  - fix openstack exec share action with correct token (same fix as commit dfc7210bda057edcb0bd22ae95b82317eb1792d4 made by Filippo on Mar 25 2025)
  - vsphere volume attributes are now preserved when updating unrelated fields

## Version 1.17.3 (2025-03-17)

Rilascio nuove funzionalità
* Aggiunto
  - shareV2 handle protocol in rule creation and deletion
* Risolto
  - vm is_running return Unable to get server status if deleted
  - map[security group delete:vm must have al least one security group]
  - openstack delete port if it doesn't exist
  - security group delete if it doesn't already exist
  - staas v1 mount target when <ip> is None
  - openstack create volume with correct token
  - adding security group to vm that has no sg
  - staas metrics avoid raising exception
  - staas removed invalid rpo 15m
  - get_tags rise exceptions
* Migliorato
  - get_linked_resources calls get_linked_resources_optimized
  - added type hints

## Version 1.17.2 (2025-03-12)

Rilascio nuove funzionalità
* Aggiunto
  - old staas v1 import management
* Risolto
  - staas size cast handle size correctly when updating
  - legacy staas fix
  - disable_logging set p_proxy_server (must be empty for private)
* Migliorato
  - staas better checks when getting snapmirrors
  - type hints

## Version 1.17.1 (2025-03-6)

Rilascio nuove funzionalità
* Aggiunto
  - manage staas-v2 volume encryption
  - manage use case config storage sites are less than compute zone available sites
* Risolto
  - bugfix staas unlink
  - nsx etag for delete rule, section
  - extend_hard_disk method
  - missing fstring that cause errors mounting volume on openstack
  - Openstack port delete

## Version 1.17.0 (2025-02-24)
rilascio funzionalità

* Aggiunto
  - staas new on_tap managment v2
  - authorization expose api only to SuperAdmin and system call
  - new orchestrator configures and new awx support and new management logic when selecting awx orchestrator on site
  - new custom  vsphere queries for get physical server
  - some optimization
  - type hints
* Risolto
  - some openapi result description and schema
  - some feature in dbaas creation (mailx, data domain, backup volume)
  - refactored encryption useing crypto utils
  - minor fixes
  - cross pod clone with different account in openstack
  - log, type hint per test private
  - wait guest tools is running before change password in creation
  - monitoring threshold get resources got timeout
  - internet gateway get resources got timeout
  - race condition when deleting Openstack port
* Rimosso
  - unused code
  - single object permissions and permtags because the api in naow only internal and used only with admibistration privilege
  - obsolete code
  - staas. manila compatibility. removed v2 dead code

## Version 1.16.9 (2025-01-08)
rilascio correttive

* Aggiunto
  - added  oracle starter pack parameter to schema
  - passing orchestrator_tag when applaying customization
  - mailx and nfs bck on oracle dbaas provisioning
* Risolto
  - fix orchestrator enable_log_module
  - fix add tag on creation
  - added tag bck while creating new oracle dbaas
* Migliorato
  - logging space delete dashboard for vm, db
  - migrated cutomization os-utility2 on new and updated awx server
  - awx job job_tags for module (logaas)

## Version 1.16.8 (2024-11-25)
rilascio correttive

* Aggiunto
  - some type hints
* Risolto
  - fix discover awx project (convert id to str)
  - bugfix rw rule for ontap nfs shares
  - alert len user group name
  - map[monitoring:disable dashboard]
  - map[haproxy:register port]
  - map[logging:comment pass_certificate]
  - orchestrator_tag in apply_customization_action_step, disable_monitoring, add pass_certificate_step
  - map[awx job:read and set step stdout]
  - enable_logging for awx02, fix job_event_msg

## Version 1.16.7 (2024-10-03)
rilascio correttive

* Risolto
  - timeout on beehive platform cmp customize run
* Migliorato
  - nuovi parameri in crazione di postgresql passati al jopb awx

## Version 1.16.6 (2024-09-23)
rilascio correttive

* Aggiunto
  - stack_v2 get attribute for  hypervisor

## Version 1.16.5 (2024-08-07)
rilascio correttive

* Aggiunto
  - Add debug log in delete rule method
  - Minor fixes
  - refactoring vsphere dfw rules
  - some check on type boolean causing erros
* Risolto
  - Ip release on vsphere Ip address when was not released if Vsphere server ext_id is None or point to unexhistent vm
  - bugfix "Add check on type boolean"
  - fix flavor in pre-import for vms with more than 1 core per cpu

## Version 1.16.4 (2024-07-09)
rilascio correttive

* Risolto
  - choose if use python3 on python discriminating on image template name and version in the DB

## Version 1.16.3 (2024-06-27)
rilascio correttive

* Aggiunto
  - Enabled server actions (e.g. change flavor) on SQLServer engine
* Migliorato
  - DNS_TTL

## Version 1.16.2 (2024-06-13)
rilascio correttive

* Risolto
  - fix install_zabbix_proxy

## Version 1.16.1 (2024-06-04)
rilascio correttive

* Risolto
  - descovering and configure of zabbix proxy
  - zabbix uri without port (if port is not present in conf)
  - manage image default min_ram_size while creating servers
  - monor fixes

## Version 1.16.0 (2024-03-26)

Rilascio nuove funzionalità
* Aggiunto
  - Debian 11 support
  - vsphere customization
  - vsphere clone
  - mariadb fix task path
  - more robust waiting customization; this has been ported on platform, use vim and vsphere api from resource it goes against our layered architecture
* Risolto
  - username and password
  - fix ubuntu username get from ssh (ubuntu or root)
  - LB add check for multiple uplink vnics
  - Correct lb import bug
  - Fix ssh authorized_keys in right location for non root users
  - Fix lb issue occurring when site-network is passed by name
  - bastion fix delete if some data aren't present
  - links find by objid
  - better logging for edge cases detection when wrong parent id
  - fix grafana sync user fornitori, fix cache resource not active
  - clone minor
  - clone add some comments
  - minor
  - clone patchset to use real admin user
  - fix username in ssh node
  - vpshere clone, this step is not needed
  - fix new server instance
  - inst new
  - redis eliminate righe commentate
  - clone add ext_id to volume resource
  - server_event_exist
  - ssh and password
  - clone funzionante stessa zona
  - hostname for server
  - clone on same zone
  - openstack check connection valid, type hint
  - fix errors
  - branch rename
  - fix bug token openstack
  - vsphere template server check
  - update changelog
  - update authors using git shortlog
  - blacked
  - headers updated
  - NPC-1011 - fix escaping range cidr in like condition e.g. %32 ->  \\\\/32

## Version 1.15.3 (2024-03-11)
rilascio correttive

* Aggiunto
  - Add funtionality to update the awx project to an existing customization
  - added new metrics vm_power_on, db_<engine>_power_on
  - Added support for mariadb
* Risolto
  - fix backup for new pods - managed no orchestrators found
  - Correct customization update removed temporary code Fix to exclude awx ge6
  - type hint ResourceCache
  - tested  resurce update for ComputeFlavor
  - fix Computeflavor.pre_update
  - fix restore point default response
  - fix Veeam reuse connection token, add debug log
  - fix private cloud vsphere only
  - fix mariadb utilizzate variabili e nomi job parlanti
  - fix image check pre_delete, param "min_ram_size"
  - update image change msg error
  - fix insert/update image
  - vsphere template server check
  - See merge request nivola/cmp2/beehive-resource!6
  - vsphere template server check
  - fix CreateCustomizationAwxProjectRequestSchema
  - MariaDB Added new classes
  - Ssh gateway remove log
  - Vpc commentato orchestrator_select_types
  - AvailabilityZone orchestrator_select_types while creating in creazione e per get hypervisor, commentato altrove
  - fix msg applied_customization Ansible connection with winrm is not supported through bastion
  - bugfix NPC-1009 NSP-1337
  - NPC-1009 NSP-1337 fix totale sbagliato dopo applicazione filtro objdef
  - type hint vpc get proxy
  - Update manifest

## Version 1.15.0 (2025-10-12)

Rilascio nuove funzionalità
* Aggiunto
  - monitoring threshold
* Risolto
  - Determine core_per_socket given vcpu
  - load balancer
  - factoring zabbix management
  - network quotas update
  - grafana dashboard in monitoring management
  - revision
  - gateway

## Version 1.14.0 (2023-06-22)

Rilascio nuove funzionalità
* Aggiunto
  - extend volume for server
* Risolto
  - fix bug that caused sync of new discovered Openstack.Image objects to fail
  - refactoring load balancer
  - user defined data and backup disks size
  - Staas in private network
  - applied customization on windows
  - veeam refactoring
  - monitoring fix check enabled
  - monitoring dbaas
  - beackup refactoring
  - fix check if monitoring is enabled too slow
  - fix vsphere stop (no task)

## Version 1.13.0 (2023-02-24)

Rilascio nuove funzionalità
* Aggiunto
  - now compute instance support static ip passed from api
  - add new async functions patch2. Use in the place of patch
  - add new async functions expunge2. Use in the place of expunge
  - add view method expunge_resource2. Use in the place of expunge_resource
  - add zabbix host do_expunge method
  - add management of security group zabbix proxy ingress rule
  - add resource api v2 with management of async internal class methods
  - add dummy_v2 entities
  - add gitlab container
  - add host_group info in provider instance. Read from openstack and vsphere
  - add sql stack info fields attributes.backup_enabled, attributes.monitoring_enabled, attributes.logging_enabled
  - improved creation of vsphere server with automatic setting of proxy for ubuntu vm
  - update flavor openstack to set extra specs
* Risolto
  - correct errors in pre_import for ComputeInstance
  - fixed problem with name propagation of ComputeLoggingSpace
  - fixed problem when create a share using manila. Now search of share type use the share type description in the place of name
  - set vsphere flavor as sync

## Version 1.12.0 (2023-01-27)

Rilascio nuove funzionalità
* Aggiunto
  - add base method to manage physical backup for Compute Instance of type openstack
  - add import api for stack sql v2
  - add support for server console in openstack, vsphere and in provider instance
  - base structure of ElasticIp [start]
  - new metrics for instances describing operating system and hypervisor instead of previous metrics describing license
  - add share label management to get custom svm
  - add new resource container ontap_netapp
  - extend provider share with orchestrator type ontap
  - add ElkPlugin, ComputeLoggingSpaceAPI, ComputeLoggingRoleAPI, ComputeLoggingRoleMappingAPI
  - add compute volume set flavor action
  - add filter by instance in security group get api
  - integrated customization_spec_name params in vsphere server creation
  - add missing task declarations in awx, openstack, zabbix
* Risolto
  - correct bug in provider image update
  - add check on flavor in compute instance import
  - security group does not get correctly instance connected
  - removed grant check in ComputeShare. Ip grant can be used also for cifs share
  - correct bug in site_network_add_subnet_step. If an allocation_pool is not configured step fails
  - fixed ComputeInstance info (like monitoring) explain
  - fixed ComputeInstance flavor info. Now flavor map exactly physical flavor
  - fixed ComputeVolume flavor info. Now flavor map exactly physical flavor
  - correct bug in ComputeRule filter
  - fixed zabbute user in postgresql sql stack
  - fixed compute availability zone expunge when some applied customizations already exist
  - fixed bug in ComputeInstance snapshot

## Version 1.11.0 (2021-06-11)

Rilascio nuove funzionalità
* Aggiunto
  - add compute instance methods to add/delete/change password to internal user
  - add api for applied customization
  - add ComputeBastion class
  - add Awx container AdHocCommand to run simple command on hosts
  - add ComputeInstance run_ad_hoc_command to run command on a vm using awx
  - add new action in SqlComputeStackV2 to get_dbs and get_users
  - integrated error propagation from awx job to applied customization
* Risolto
  - fixed gateway errors when is evaluated subnet to use with vpc interpod
  - add Compute SecurityGroup method to get_rules
  - add Compute SecurityGroup check of existing rule in pre_delete
  - fixed creation of ComputeInstance with public network. Now multi avz is set automatically to false
  - add Compute Share get_quotas
  - correct bug during openstack volume remove. State was forced to available
  - fixed bug in openstack server clone in different pod
  - correct step create_zone_instance_step return that block task
  - correct bug in dns recorda and recordcname that block add record when name overlap between different zones
  - correct bug in get_aggregated_resource_from_physical_resource. If physical resource is linked to more than one aggregated resource is necessary a parent filter to select the correct one.
  - correct bug to compute rule. Now only active availability zones are used during creation

## Version 1.10.0 (2021-02-05)

Rilascio nuove funzionalità
* Aggiunto
  - add filter for hypervisor in compute instance api
  - add the concept of bastion host in compute zone
  - add new api ping (with sql check), capabilities and version to /v1.0/nrs
  - add create openstack server from existing volume in the same container or in another container
  - add create openstack volume from existing volume in the same container or in another container
  - add create compute instance from existing volume in the same container or in another container
  - add compute instance methods to manage internal user [beta]
  - integrated check method in volume, server, compute instance and compute volume
  - add link id in resource tree
* Risolto
  - fixed bug in discover and synchronize openstack volume. List was limited to 1000 items
  - fixed bug in get quotas for sql stack v2. Ram was calculated in MB.
  - update openstack volume client with volume_v3 that use cinder v3 api
  - improved response time of stack_v2 list api
  - improved response time of ssql_tack_v2 list api
  - fixed sql stack creation in private compute zone. Must be configured (for the moment manually) a bastion host
  - improved response time of compute_instance list api
  - apply patch in server_expunge_physical_step. When ext_id is not valid get_ports got error
  - correct check of manage status of a ComputeInstance during creation
  - correct some bug in compute volume info
  - correct some bugs in openstack container to support stein version

## Version 1.9.0 (2020-10-23)

Rilascio nuove funzionalità
* Aggiunto
  - add sql_stack_v2 with sql stack based on stack_v2
  - added change of security group in openstack server
  - added change of security group in vsphere server
  - added openstack server snapshot add/remove/revert
  - added vsphere server snapshot add/remove/revert
  - added provider instance snapshot add/remove/revert
  - added create and delete of openstack share based on share network and local share server
  - added create and delete of provider share based on share network and local share server
  - add resource entity api to clean cache
  - fixed error generating swagger specification
  - integrated api to set check quotas and metrics for resource
* Risolto
  - fixed creation of vsphere server. If a template has more then one disk it is not registered

## Version 1.8.1 (2020-07-14)

Rilascio nuove funzionalità
* Aggiunto
  - ComputeGateway attach/detach vpc
  - ComputeGateway set default internet ruote
  - ComputeGateway manage firewall rules
  - ComputeGateway manage nat rules
  - ComputeGateway manage credentials
* Risolto
  - removed check quotas. Leave check only on service component
  - improved compute zone get metrics reducing overhead and adding metrics cache
  - improved security group rules list from api
  - ComputeGateway crud
  - Create Virtual Machine on private network
  - ping method in Awx container and Zabbix container
  - correct api of Customization and AppliedCustomization
  - Correct info and detail bug in openstack image
  - Correct delete of datastore from vsphere volume type. Used Link.expunge instead of Link.delete
  - Correct bug in get_paginated_entities that return wrong number of records
  - Correct bug in site orchestrator delete for type Awx and Zabbix

## Version 1.8.0 (2020-06-21)

Rilascio nuove funzionalità
* Aggiunto
  - new task_v2 for all the package
  - add scheduled start e stop for compute instance
  - add vpc_v2 with private vpc management
  - add ComputeCustomization
  - add ComputeGateway
  - add stack_v2 with stack management make by provider container
* Risolto
  - porting of all code to python 3 - Correct various bugs

## Version 1.7.0 (2019-09-04)

Rilascio nuove funzionalità
* Risolto
  - replacemetent of vsphere task with task_v2
  - correct bug when deleting openstack server. A port remained hanging
  - correct bug that blocks deletion of virtual machine when dns zone was not found
  - correct bug in post api of site_network. dns_search param is not read
  - correct bug in stack resource list. Volume with volume attachment is showed two times
  - correct bug in site-network append platform network
  - correct bug in vsphere datastore synchronization

## Version 1.6.0 (2019-09-04)

Rilascio nuove funzionalità
* Aggiunto
  - added management of compute volume snapshots
  - added import ComputeShare
  - added import ComputeInstance
  - added import ComputeVolume
  - assign trilio_backup_role to admin user when create a new project
* Risolto
  - revisionata api /v1.0/nrs/provider/site_networks/<oid>/network [PUT] per appendere reti di tipo vsphere e openstack
  - corretto il controllo della chiave ssh negli app_stack e sql_stack. Se non si trova openstack_name negli attributes viene fornito un errore. Senza la chiave in openstack heat non è in grado di generare lo stack
  - changed delete task of openstack volume, openstack instance and openstack stack to remove all the snapshots of the volumes
  - revisione generale api site-network
  - revisione e semplificazione dei metodi get_resource e get_resources
* Rimosso
  - method ResourceController.get_errors()
  - method ResourceController.get_parent_resource_index()

## Version 1.5.0 (2019-05-24)
rilascio funzionalità

* Aggiunto
  - aggiunto openstack VolumeType
  - OpenstackVolume revisione generale
  - OpenstackImage aggiunta lista metadati
  - aggiunto vsphere VolumeType
  - aggiunto vsphere Volume
  - aggiunto ComputeVolumeFlavor
  - aggiunto ComputeVolume
  - aggiunto metodo patch per una ComputeInstance
  - aggiunte api di add e del volume ad una ComputeInstance
  - aggiunta api di modifica state di una Resource
  - aggiunto campo last_error nel model Resource. Utilizzo di questo campo per salvare l'ultimo errore
  - aggiunta api su slq_stack che restituisce la lista degli engine
  - aggiunto parametro host_group nei server per indicare il cluster di allocazione in vsphere
  - modificata creazione server openstack. Adesso la creazione dei volumi si può fare a partire a un'immagine, da un volume esistente o da un snapshot. I volumi supportano i volume type
  - modificata la creazione delle ComputeInstance per agganciare i ComputeVolume con type=openstack
* Risolto
  - modificato metdodo container.get_resource. Adesso setta direttamente il parent container e imposta il parent solo se details è True
  - ottimizzate list e get di OpenstackServer, OpenstackVolume, OpenstackHeatStack

## Version 1.4.0 (2019-02-27)
rilascio funzionalità

* Aggiunto
  - ComputeImage aggiunta minima dimensione disco immagine e elenco di hypervisor per zona
  - Aggiunto container dns
* Risolto
  - app stack rivista struttura generale - corretti bug nella cancellazione dei security group - corretti bug nella creazione delle rule vsphere - corretto un bug nella cancellazione dei server openstack

## Version 1.3.0 (2019-02-01)
rilascio funzionalità

* Aggiunto
  - ComputeZone aggiunta assegnazione automatica del ruolo master del gruppo ssh di una ComputeZone managed allo user o group specificato nel campo facoltativo managed_by
  - ComputeZone aggiunta api che restituisce le availability zones
  - ComputeZone rivista creazione section vsphere nsx dfw e folder vsphere
  - ComputeServer rivista creazione server vsphere
  - ComputeRule rivista creazione rule vsphere nsx dfw
* Risolto
  - corretto bug nell'action di set_quotas della compute zone

## Version 1.2.0 (2019-01-13)
rilascio funzionalità

* Aggiunto
  - resource job aggiunta registrazione del job sul container oltre che sulla risorsa
  - compute security group ottimizzati i metodi di interrogazioni
  - compute stack rivista struttura generale
  - compute share rivista struttura generale

## Version 1.1.0 (2018-07-31)
rilascio funzionalità

* Aggiunto
  - inizio revisione job di creazione. Rivisto la crreazione dei job. Cambio di invocazione di job da altri job. Non avviene più invocando l’api ma direttamente invocando il job.
  - openstack aggiunta gestione action (start, stop, reboot, add-volume, del-volume, set-flavor)
  - compute instance aggiunta gestione action (start, stop, set-flavor)

## Version 1.0.0 (2018-07-31)
First production preview release.


## Version 0.1.0 (2016-4-28)
First private preview release.

