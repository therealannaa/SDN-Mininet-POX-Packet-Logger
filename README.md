# SDN Packet Monitoring and Control using Mininet and POX

## What is this project? (Simple explanation)

In a normal network, each switch decides on its own how to forward packets — the rules are hardcoded in hardware. You cannot easily change them.

**SDN (Software Defined Networking)** changes this: it removes the decision-making brain from the switch and puts it in a Python program (the controller) running on your computer. The switch just asks "what should I do with this packet?" and the controller decides.

This project builds a small fake network using **Mininet** (a tool that simulates hosts, switches and cables entirely in software on Linux), controlled by **POX** (a Python SDN controller). The controller watches every packet, blocks ICMP (ping), allows TCP, and writes a log of everything.

---

## Problem Statement

This project implements a Software Defined Networking (SDN) solution using Mininet and the POX controller. The controller monitors network traffic, identifies protocols, blocks ICMP packets, allows TCP traffic, and logs packet information into a CSV file.

---

## Objective

- Demonstrate controller–switch interaction over OpenFlow
- Design match–action flow rules in software
- Observe and filter network traffic in real time
- Log all packet decisions to a CSV file for analysis

---

## Tools and Technologies Used

| Tool | Purpose |
|------|---------|
| Mininet | Simulates hosts, switches, and links entirely in software |
| POX Controller | Python-based SDN controller that installs flow rules |
| OpenFlow 1.0 | Protocol used for controller ↔ switch communication |
| Open vSwitch (OVS) | The software switch used inside Mininet |
| iperf | Measures TCP throughput between hosts |
| Python 3 | Language for the controller and topology scripts |
| Linux / WSL | Operating environment |

---

## Network Topology

```
         [ POX Controller ]
         127.0.0.1 : 6633
               |
           OpenFlow
               |
          [ s1 Switch ]
         /      |      \
     port1   port2   port3
       |        |        |
      h1       h2       h3
  10.0.0.1  10.0.0.2  10.0.0.3
```

- 3 hosts: h1, h2, h3
- 1 OVS switch: s1
- 1 remote controller: POX (c0)

---

## How SDN Works — Step by Step (Plain English)

### What happens when h1 sends a packet to h2?

1. **h1 sends a packet** → the packet arrives at switch s1
2. **s1 checks its flow table** → no matching rule exists yet
3. **s1 sends a PacketIn event** to the POX controller
4. **POX runs your Python code:**
   - Records h1's MAC and port (MAC learning)
   - Identifies the protocol (ARP? ICMP? TCP?)
   - Checks if the protocol is in the block list
5. **If ICMP:** POX installs a DROP rule → packet is thrown away
6. **If TCP/ARP and destination is known:** POX installs a FORWARD rule and sends the packet out the correct port
7. **If destination is unknown:** POX floods the packet out all ports
8. **Everything is written to packet_log.csv**

### Why does ICMP get blocked?

In `packet_logger.py`, there is a single Python list:
```python
BLOCKED_PROTOCOLS = ["ICMP"]
```
When the controller sees ICMP, it sends back a flow rule with an **empty actions list**. In OpenFlow, no action = drop. This blocks all future ICMP from the switch without the packet ever reaching the controller again.

### What is a flow rule?

A flow rule is like an instruction card placed inside the switch:
> "If you see a TCP packet from h1 to h2, send it out port 2. Keep this rule for 10 seconds."

After the first packet, the switch handles everything itself at full speed — no controller trip needed. This is why TCP gets **34 Gbits/sec** throughput.

---

## Project Files

### `custom_topo.py`
Defines the network. Creates h1, h2, h3, switch s1, links them together, and connects to the POX controller at 127.0.0.1:6633.

```python
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

class PacketLoggerTopo(Topo):
    def build(self):
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        s1 = self.addSwitch('s1')
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)

def run():
    topo = PacketLoggerTopo()
    net = Mininet(
        topo=topo,
        controller=RemoteController('c0', ip='127.0.0.1', port=6633),
        switch=OVSSwitch
    )
    net.start()
    info("*** Network Started\n")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()
```

### `packet_logger.py`
The POX controller module. Key logic:

```python
BLOCKED_PROTOCOLS = ["ICMP"]   # <-- change this to block any protocol

def _handle_PacketIn(self, event):
    # Step 1: Learn source MAC
    mac_table[dpid][src_mac] = in_port

    # Step 2: Identify protocol (ARP / ICMP / TCP / UDP / OTHER)
    eth_type, protocol, src_ip, dst_ip, src_port, dst_port = identify_protocol(packet)

    # Step 3: Block if needed
    if protocol in BLOCKED_PROTOCOLS:
        install_flow_rule(event, None, protocol)   # empty actions = DROP
        return

    # Step 4: Forward or flood
    if dst_mac in mac_table[dpid]:
        install_flow_rule(event, out_port, protocol)   # FORWARD
    else:
        flood(event)   # FLOODED

    # Step 5: Log everything to CSV
    log_packet(...)
```

---

## How to Run the Project

### Step 1 — Install and verify POX

```bash
cd ~
git clone https://github.com/noxrepo/pox
cd pox
python3 pox.py --version
```

**Screenshot evidence — POX cloned and verified:**

![POX installed and version confirmed](screenshots/1_pox_install.png)

POX 0.7.0 (gar) confirmed. Copy `packet_logger.py` into `~/pox/ext/`.

---

### Step 2 — Start the POX controller

Open **Terminal 1**:

```bash
cd ~/pox
python3 pox.py log.level --DEBUG openflow.of_01 packet_logger
```

Leave this running. It listens on port 6633 and waits for switches to connect.

---

### Step 3 — Start the Mininet topology

Open **Terminal 2**:

```bash
cd ~/mininet_topo
sudo python3 custom_topo.py
```

**Screenshot evidence — Mininet started successfully:**

![Mininet topology running with h1 h2 h3 s1 c0](screenshots/2_mininet_start.png)

Mininet creates the network, adds h1 h2 h3, adds s1, adds links, starts controller c0, and opens the CLI. The `nodes` command confirms: `c0 h1 h2 h3 s1` — all 5 nodes are alive.

---

## Test Scenarios

### Test Scenario 1 — ICMP Blocked (Ping)

**Command:**
```
mininet> h1 ping h2 -c 5
```

**Screenshot evidence — 100% packet loss:**

![h1 ping h2 showing 100% packet loss](screenshots/3_ping_blocked_iperf.png)

**Result:**
```
5 packets transmitted, 0 received, 100% packet loss, time 4099ms
```

**Why this happens:**
1. h1 sends ARP to discover h2's MAC — this is FLOODED (destination unknown)
2. h2 replies — this is FORWARDED, MAC is now learned
3. h1 sends ICMP echo → controller identifies ICMP → installs DROP rule → **blocked**
4. All subsequent pings are dropped by the switch itself (flow rule active)

This proves the controller is enforcing policy.

---

### Test Scenario 2 — TCP Allowed (iperf)

**Commands:**
```
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2
```

**Screenshot evidence — TCP succeeds with high throughput:**

![iperf showing 34.3 Gbits/sec TCP throughput](screenshots/3_ping_blocked_iperf.png)

**Result:**
```
[ 1] local 10.0.0.1 port 42032 connected with 10.0.0.2 port 5001
[ 1]  0.0000-10.0040 sec  40.0 GBytes  34.3 Gbits/sec
```

**Why this works:**
1. h1 connects to h2 on TCP port 5001
2. Controller identifies TCP — not in BLOCKED_PROTOCOLS
3. Flow rule installed: FORWARD out port 2
4. Subsequent TCP packets handled by switch at full speed
5. Result: 34.3 Gbits/sec throughput over 10 seconds

---

## Switch Verification Commands

### View switch port details

```
mininet> sh ovs-ofctl show s1
```

**Screenshot evidence:**

![ovs-ofctl show s1 output](screenshots/4_ovs_show.png)

Shows:
- `dpid: 0000000000000001` — switch ID used by POX
- `1(s1-eth1)` — port 1 connected to h1
- `2(s1-eth2)` — port 2 connected to h2
- `3(s1-eth3)` — port 3 connected to h3
- All ports at 10GB-FD (full duplex)

---

### View port traffic statistics

```
mininet> sh ovs-ofctl dump-ports s1
```

**Screenshot evidence:**

![dump-ports showing rx/tx packet counts](screenshots/5_dump_ports.png)

Shows actual packet counts per port — confirms real traffic was flowing:
- s1-eth1: rx 13 pkts, tx 32 pkts
- s1-eth2: rx 12 pkts, tx 32 pkts
- s1-eth3: rx 11 pkts, tx 32 pkts

---

### View network wiring

```
mininet> net
```

**Screenshot evidence:**

![net command showing all links](screenshots/6_net_dpctl.png)

Confirms exact wiring:
```
h1 h1-eth0:s1-eth1
h2 h2-eth0:s1-eth2
h3 h3-eth0:s1-eth3
s1 lo: s1-eth1:h1-eth0  s1-eth2:h2-eth0  s1-eth3:h3-eth0
```

Also shows `dpctl dump-flows` output — the flow rules POX installed on the switch.

---

### View switch details (second session)

**Screenshot evidence:**

![ovs-ofctl show s1 second run](screenshots/7_ovs_show2.png)

Confirms switch capabilities: FLOW_STATS, TABLE_STATS, PORT_STATS, QUEUE_STATS, ARP_MATCH_IP — all OpenFlow 1.0 features required for this project are present.

---

## Packet Log

All traffic is written to `~/packet_log.csv` automatically.

**Screenshot evidence — raw CSV in terminal:**

![packet_log.csv contents](screenshots/8_packet_log_csv.png)

### CSV columns explained

| Column | Meaning |
|--------|---------|
| timestamp | When the packet was seen |
| switch_dpid | Which switch (always 00-00-00-00-00-01 = s1) |
| in_port | Which port the packet came in on |
| src_mac | Source MAC address |
| dst_mac | Destination MAC address |
| eth_type | EtherType (0x0800=IPv4, 0x0806=ARP, 0x86dd=IPv6) |
| protocol | ARP / ICMP / TCP / UDP / OTHER |
| src_ip | Source IP (N/A for non-IP) |
| dst_ip | Destination IP |
| src_port | TCP/UDP source port (N/A otherwise) |
| dst_port | TCP/UDP destination port |
| action | FLOODED / FORWARDED / BLOCKED |

### Sample log entries

```
Timestamp             Switch          Port  Src MAC            Dst MAC            Type    Proto  Src IP    Dst IP    Action
2026-04-15 04:57:22   00-00-00-00-00-01  1  42:be:a6:6b:43:f7  ff:ff:ff:ff:ff:ff  0x0806  ARP    10.0.0.1  10.0.0.2  FLOODED
2026-04-15 04:57:22   00-00-00-00-00-01  2  16:d0:1f:ee:9c:a5  42:be:a6:6b:43:f7  0x0806  ARP    10.0.0.2  10.0.0.1  FORWARDED
2026-04-15 04:57:22   00-00-00-00-00-01  1  42:be:a6:6b:43:f7  16:d0:1f:ee:9c:a5  0x0800  ICMP   10.0.0.1  10.0.0.2  BLOCKED
2026-04-15 04:59:14   00-00-00-00-00-01  1  42:be:a6:6b:43:f7  16:d0:1f:ee:9c:a5  0x0800  TCP    10.0.0.1  10.0.0.2  FORWARDED
2026-04-15 04:59:14   00-00-00-00-00-01  2  16:d0:1f:ee:9c:a5  42:be:a6:6b:43:f7  0x0800  TCP    10.0.0.2  10.0.0.1  FORWARDED
```

### Log summary (from actual run)

| Action | Count | Explanation |
|--------|-------|-------------|
| FLOODED | 90 | Mostly IPv6 multicast (normal in Mininet) + initial ARP broadcasts |
| FORWARDED | 8 | ARP replies + TCP data packets in both directions |
| BLOCKED | 3 | All ICMP packets from h1 to h2 |

---

## Controller Logic — Flow Diagram

```
PacketIn Event received
        |
        v
Learn source MAC → mac_table[dpid][src_mac] = in_port
        |
        v
Identify protocol
   (ARP / ICMP / TCP / UDP / OTHER)
        |
   +----+----+
   |         |
ICMP       Other
   |         |
   v         v
BLOCKED   Dst MAC known?
Install    /         \
DROP      YES        NO
rule       |          |
           v          v
       FORWARD      FLOOD
       Install      out all
       flow rule    ports
           |
           v
     Log to CSV
```

---

## Why the IPv6 Entries Show "FLOODED"

You will notice most log entries are `OTHER` protocol with `0x86dd` (IPv6) — these are normal IPv6 Neighbor Discovery multicast packets that all Linux hosts send automatically. Since the controller does not have a specific rule for them (and destination MACs like `33:33:xx:xx:xx:xx` are IPv6 multicast addresses), they get flooded. This is expected and harmless behavior in Mininet.

---

## Key Results Summary

| Test | Command | Result | Proves |
|------|---------|--------|--------|
| ICMP blocked | `h1 ping h2 -c 5` | 100% packet loss | Controller DROP rule works |
| TCP allowed | `h1 iperf -c 10.0.0.2` | 34.3 Gbits/sec | Controller FORWARD rule works |
| Logging | `cat ~/packet_log.csv` | All packets recorded | CSV logging works |
| Flow rules | `sh ovs-ofctl dump-flows` | Rules visible on switch | OpenFlow communication works |

---

## Conclusion

This project successfully demonstrates SDN-based traffic control using Mininet and the POX controller:

- The controller implements **protocol-aware filtering** — ICMP is blocked by a single Python list, TCP is allowed
- **MAC learning** means the switch builds up knowledge of the network and forwards without flooding
- **Flow rules** are installed on the switch so repeated packets are handled at hardware speed without bothering the controller
- **Full packet logging** to CSV provides visibility that a traditional switch cannot offer
- The entire policy (what to block, what to allow) lives in Python code — changing it requires no hardware reconfiguration

This demonstrates the core SDN value: network intelligence in software, not locked in device hardware.
