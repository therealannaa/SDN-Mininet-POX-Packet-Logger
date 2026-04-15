"""
SDN Packet Logger - POX Controller
Captures and logs packet headers, identifies protocol types,
maintains logs, and installs flow rules.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.packet import ethernet, ipv4, tcp, udp, icmp, arp
import datetime
import csv
import os

log = core.getLogger()

# Path for the CSV log file
LOG_FILE = os.path.expanduser("~/packet_log.csv")

# Protocols to BLOCK (test scenario 2: blocked vs allowed)
BLOCKED_PROTOCOLS = ["ICMP"]

# MAC table for learning switch behavior
mac_table = {}  # {dpid: {mac: port}}


def write_csv_header():
    """Create CSV file and write header row."""
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "switch_dpid", "in_port",
            "src_mac", "dst_mac", "eth_type",
            "protocol", "src_ip", "dst_ip",
            "src_port", "dst_port", "action"
        ])


def log_packet(dpid, in_port, src_mac, dst_mac, eth_type,
               protocol, src_ip, dst_ip, src_port, dst_port, action):
    """Append one row to the CSV log and print to console."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    row = [
        timestamp, dpid_to_str(dpid), in_port,
        src_mac, dst_mac, eth_type,
        protocol, src_ip, dst_ip,
        src_port, dst_port, action
    ]
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    log.info(
        f"[{action}] {protocol} | {src_ip}:{src_port} -> "
        f"{dst_ip}:{dst_port} | switch={dpid_to_str(dpid)} port={in_port}"
    )


def identify_protocol(packet):
    """
    Extract protocol name and layer-4 info from an Ethernet packet.
    Returns: (eth_type_str, protocol, src_ip, dst_ip, src_port, dst_port)
    """
    src_ip = dst_ip = src_port = dst_port = "N/A"
    protocol = "OTHER"
    eth_type = "0x{:04x}".format(packet.type)

    if packet.type == ethernet.ARP_TYPE:
        protocol = "ARP"
        arp_pkt = packet.payload
        if isinstance(arp_pkt, arp):
            src_ip = str(arp_pkt.protosrc)
            dst_ip = str(arp_pkt.protodst)

    elif packet.type == ethernet.IP_TYPE:
        ip_pkt = packet.payload
        if isinstance(ip_pkt, ipv4):
            src_ip = str(ip_pkt.srcip)
            dst_ip = str(ip_pkt.dstip)

            if isinstance(ip_pkt.payload, tcp):
                protocol = "TCP"
                src_port = str(ip_pkt.payload.srcport)
                dst_port = str(ip_pkt.payload.dstport)

            elif isinstance(ip_pkt.payload, udp):
                protocol = "UDP"
                src_port = str(ip_pkt.payload.srcport)
                dst_port = str(ip_pkt.payload.dstport)

            elif isinstance(ip_pkt.payload, icmp):
                protocol = "ICMP"

    return eth_type, protocol, src_ip, dst_ip, src_port, dst_port


def install_flow_rule(event, out_port, protocol):
    """Install a proactive flow rule on the switch."""
    msg = of.ofp_flow_mod()
    msg.match = of.ofp_match.from_packet(event.parsed, event.port)
    msg.idle_timeout = 10   # seconds
    msg.hard_timeout = 30
    msg.priority = 100

    if protocol in BLOCKED_PROTOCOLS:
        # Drop action (empty actions list = drop)
        msg.actions = []
        log.info(f"Flow rule installed: DROP {protocol}")
    else:
        msg.actions.append(of.ofp_action_output(port=out_port))
        log.info(f"Flow rule installed: FORWARD {protocol} → port {out_port}")

    event.connection.send(msg)


def flood(event):
    """Send packet out all ports (flood)."""
    msg = of.ofp_packet_out()
    msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
    msg.data = event.ofp
    msg.in_port = event.port
    event.connection.send(msg)


class PacketLoggerSwitch(object):
    """
    Per-switch handler. Implements:
    - MAC learning table
    - Protocol identification and logging
    - Selective blocking (ICMP dropped)
    - Flow rule installation
    """

    def __init__(self, connection):
        self.connection = connection
        self.dpid = connection.dpid
        mac_table[self.dpid] = {}
        connection.addListeners(self)
        log.info(f"Switch {dpid_to_str(self.dpid)} connected.")

    def _handle_PacketIn(self, event):
        """
        Called on every packet_in event.
        This is the core SDN control plane logic.
        """
        packet = event.parsed
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        in_port = event.port
        dpid = event.connection.dpid
        src_mac = str(packet.src)
        dst_mac = str(packet.dst)

        # Learn source MAC
        mac_table[dpid][src_mac] = in_port

        # Identify protocol and extract headers
        eth_type, protocol, src_ip, dst_ip, src_port, dst_port = identify_protocol(packet)

        # Decide action
        if protocol in BLOCKED_PROTOCOLS:
            action = "BLOCKED"
            log_packet(dpid, in_port, src_mac, dst_mac, eth_type,
                       protocol, src_ip, dst_ip, src_port, dst_port, action)
            # Install drop rule
            install_flow_rule(event, None, protocol)
            return  # Do not forward

        # Look up destination MAC
        if dst_mac in mac_table[dpid]:
            out_port = mac_table[dpid][dst_mac]
            action = "FORWARDED"
            log_packet(dpid, in_port, src_mac, dst_mac, eth_type,
                       protocol, src_ip, dst_ip, src_port, dst_port, action)
            install_flow_rule(event, out_port, protocol)
            # Send this buffered packet
            msg = of.ofp_packet_out()
            msg.actions.append(of.ofp_action_output(port=out_port))
            msg.data = event.ofp
            msg.in_port = in_port
            event.connection.send(msg)
        else:
            action = "FLOODED"
            log_packet(dpid, in_port, src_mac, dst_mac, eth_type,
                       protocol, src_ip, dst_ip, src_port, dst_port, action)
            flood(event)


class PacketLogger(object):
    """Top-level component registered with POX core."""

    def __init__(self):
        write_csv_header()
        log.info(f"Packet Logger started. Logging to {LOG_FILE}")
        log.info(f"Blocking protocols: {BLOCKED_PROTOCOLS}")
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        """A new switch connected — create a handler for it."""
        PacketLoggerSwitch(event.connection)


def launch():
    """Entry point called by POX."""
    core.registerNew(PacketLogger)
