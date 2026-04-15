# SDN Packet Monitoring and Control using Mininet and POX

## Problem Statement

This project implements a Software Defined Networking (SDN) solution using Mininet and the POX controller. The controller monitors network traffic, identifies protocols, blocks ICMP packets, allows TCP traffic, and logs packet information into a CSV file.

---

## Objective

The objective of this project is to demonstrate:

* Controller–switch interaction
* Flow rule design using match–action logic
* Network behavior observation
* Traffic filtering and monitoring

---

## Tools and Technologies Used

* Mininet
* POX Controller
* Python
* OpenFlow
* iperf
* Linux / WSL

---

## Network Topology

The network consists of:

* 3 Hosts:

  * h1
  * h2
  * h3
* 1 Switch:

  * s1
* 1 Controller:

  * POX

Topology structure:

h1
\
s1
/
h2

and

h3 connected to s1

---

## Controller Logic

The controller performs the following tasks:

1. Listens for PacketIn events
2. Identifies the protocol type
3. Blocks ICMP packets
4. Allows TCP packets
5. Logs packet information into a CSV file

---

## How to Run the Project

Start the POX controller:

python3 pox.py log.level --DEBUG openflow.of_01 packet_logger

Start the Mininet topology:

cd ~/mininet_topo
sudo python3 custom_topo.py

---

## Test Scenario 1 — ICMP Blocked

Command:

h1 ping h2 -c 5

Result:

100% packet loss

This demonstrates that ICMP traffic is blocked by the controller.

---

## Test Scenario 2 — TCP Allowed

Commands:

h2 iperf -s &
h1 iperf -c 10.0.0.2

Result:

High throughput observed

This demonstrates that TCP traffic is allowed.

---

## Packet Logging

Packet information is stored in:

packet_log.csv

Example:

TCP,FORWARDED
ICMP,BLOCKED

---

## Expected Output

* ICMP traffic should be blocked
* TCP traffic should be allowed
* Packet details should be logged in CSV file

---

## Conclusion

This project successfully demonstrates SDN-based traffic control using Mininet and the POX controller. The controller applies protocol-based filtering and logs network activity for monitoring and analysis.
