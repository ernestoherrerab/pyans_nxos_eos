# router-bgp-vrf-lite
# Table of Contents
<!-- toc -->

- [Management](#management)
  - [Management Interfaces](#management-interfaces)
- [Authentication](#authentication)
- [Monitoring](#monitoring)
- [Internal VLAN Allocation Policy](#internal-vlan-allocation-policy)
  - [Internal VLAN Allocation Policy Summary](#internal-vlan-allocation-policy-summary)
- [Interfaces](#interfaces)
- [Routing](#routing)
  - [IP Routing](#ip-routing)
  - [IPv6 Routing](#ipv6-routing)
  - [Static Routes](#static-routes)
  - [Router BGP](#router-bgp)
- [Multicast](#multicast)
- [Filters](#filters)
  - [Prefix-lists](#prefix-lists)
  - [Route-maps](#route-maps)
- [ACL](#acl)
- [Quality Of Service](#quality-of-service)

<!-- toc -->
# Management

## Management Interfaces

### Management Interfaces Summary

#### IPv4

| Management Interface | description | Type | VRF | IP Address | Gateway |
| -------------------- | ----------- | ---- | --- | ---------- | ------- |
| Management1 | oob_management | oob | MGMT | 10.73.255.122/24 | 10.73.255.2 |

#### IPv6

| Management Interface | description | Type | VRF | IPv6 Address | IPv6 Gateway |
| -------------------- | ----------- | ---- | --- | ------------ | ------------ |
| Management1 | oob_management | oob | MGMT | -  | - |

### Management Interfaces Device Configuration

```eos
!
interface Management1
   description oob_management
   vrf MGMT
   ip address 10.73.255.122/24
```

# Authentication

# Monitoring

# Internal VLAN Allocation Policy

## Internal VLAN Allocation Policy Summary

**Default Allocation Policy**

| Policy Allocation | Range Beginning | Range Ending |
| ------------------| --------------- | ------------ |
| ascending | 1006 | 4094 |

# Interfaces

# Routing

## IP Routing

### IP Routing Summary

| VRF | Routing Enabled |
| --- | --------------- |
| default | false|
### IP Routing Device Configuration

```eos
```
## IPv6 Routing

### IPv6 Routing Summary

| VRF | Routing Enabled |
| --- | --------------- |
| default | false |

## Static Routes

### Static Routes Summary

| VRF | Destination Prefix | Next Hop IP             | Exit interface      | Administrative Distance       | Tag               | Route Name                    | Metric         |
| --- | ------------------ | ----------------------- | ------------------- | ----------------------------- | ----------------- | ----------------------------- | -------------- |
| BLUE-C1  | 193.1.0.0/24 |  -  |  Null0  |  1  |  -  |  -  |  - |
| BLUE-C1  | 193.1.1.0/24 |  -  |  Null0  |  1  |  -  |  -  |  - |
| BLUE-C1  | 193.1.2.0/24 |  -  |  Null0  |  1  |  -  |  -  |  - |

### Static Routes Device Configuration

```eos
!
ip route vrf BLUE-C1 193.1.0.0/24 Null0
ip route vrf BLUE-C1 193.1.1.0/24 Null0
ip route vrf BLUE-C1 193.1.2.0/24 Null0
```

## Router BGP

### Router BGP Summary

| BGP AS | Router ID |
| ------ | --------- |
| 65001|  1.0.1.1 |

| BGP Tuning |
| ---------- |
| no bgp default ipv4-unicast |
| distance bgp 20 200 200 |
| graceful-restart restart-time 300 |
| graceful-restart |

### Router BGP Peer Groups

#### OBS_WAN

| Settings | Value |
| -------- | ----- |
| Address Family | ipv4 |
| Remote AS | 65000 |

#### SEDI

| Settings | Value |
| -------- | ----- |
| Address Family | ipv4 |
| Remote AS | 65003 |
| Source | Loopback101 |
| Ebgp multihop | 10 |

#### WELCOME_ROUTERS

| Settings | Value |
| -------- | ----- |
| Address Family | ipv4 |
| Remote AS | 65001 |

### BGP Neighbors

| Neighbor | Remote AS | VRF |
| -------- | --------- | --- |
| 10.1.1.0 | Inherited from peer group OBS_WAN | BLUE-C1 |
| 10.255.1.1 | Inherited from peer group WELCOME_ROUTERS | BLUE-C1 |
| 101.0.3.1 | Inherited from peer group SEDI | BLUE-C1 |

### Router BGP EVPN Address Family

#### Router BGP EVPN MAC-VRFs

#### Router BGP EVPN VRFs

| VRF | Route-Distinguisher | Redistribute |
| --- | ------------------- | ------------ |
| BLUE-C1 | 1.0.1.1:101 | static |

### Router BGP Device Configuration

```eos
!
router bgp 65001
   router-id 1.0.1.1
   no bgp default ipv4-unicast
   distance bgp 20 200 200
   graceful-restart restart-time 300
   graceful-restart
   neighbor OBS_WAN description BGP Connection to OBS WAN CPE
   neighbor OBS_WAN peer group
   neighbor OBS_WAN remote-as 65000
   neighbor SEDI description BGP Connection to OBS WAN CPE
   neighbor SEDI peer group
   neighbor SEDI remote-as 65003
   neighbor SEDI update-source Loopback101
   neighbor SEDI ebgp-multihop 10
   neighbor WELCOME_ROUTERS description BGP Connection to WELCOME ROUTER 02
   neighbor WELCOME_ROUTERS peer group
   neighbor WELCOME_ROUTERS remote-as 65001
   redistribute static
   !
   address-family ipv4
      neighbor OBS_WAN activate
      neighbor SEDI route-map RM-BGP-EXPORT-DEFAULT-BLUE-C1 out
      neighbor SEDI activate
      neighbor WELCOME_ROUTERS activate
   !
   vrf BLUE-C1
      rd 1.0.1.1:101
      neighbor 10.1.1.0 peer group OBS_WAN
      neighbor 10.255.1.1 peer group WELCOME_ROUTERS
      neighbor 10.255.1.1 weight 65535
      neighbor 101.0.3.1 peer group SEDI
      neighbor 101.0.3.1 weight 100
      redistribute static
      aggregate-address 0.0.0.0/0 as-set summary-only attribute-map RM-BGP-AGG-APPLY-SET
      aggregate-address 193.1.0.0/16 as-set summary-only attribute-map RM-BGP-AGG-APPLY-SET
      !
      comment
      Comment created from eos_cli under router_bgp.vrfs.BLUE-C1
      EOF

```

# Multicast

# Filters

## Prefix-lists

### Prefix-lists Summary

#### PL-BGP-DEFAULT-BLUE-C1

| Sequence | Action |
| -------- | ------ |
| 10 | permit 0.0.0.0/0 le 1 |

### Prefix-lists Device Configuration

```eos
!
ip prefix-list PL-BGP-DEFAULT-BLUE-C1
   seq 10 permit 0.0.0.0/0 le 1
```

## Route-maps

### Route-maps Summary

#### RM-BGP-AGG-APPLY-SET

| Sequence | Type | Match and/or Set |
| -------- | ---- | ---------------- |
| 10 | permit | set local-preference 50 |

#### RM-BGP-EXPORT-DEFAULT-BLUE-C1

| Sequence | Type | Match and/or Set |
| -------- | ---- | ---------------- |
| 10 | permit | match ip address prefix-list PL-BGP-DEFAULT-BLUE-C1 |

### Route-maps Device Configuration

```eos
!
route-map RM-BGP-AGG-APPLY-SET permit 10
   description RM for BGP AGG Set
   set local-preference 50
!
route-map RM-BGP-EXPORT-DEFAULT-BLUE-C1 permit 10
   description RM for BGP default route in BLUE-C1
   match ip address prefix-list PL-BGP-DEFAULT-BLUE-C1
```

# ACL

# Quality Of Service
