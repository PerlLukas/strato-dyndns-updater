#!/usr/bin/env python3

import base64
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

DOMAIN = "example.com"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")


def load_credentials():
    creds = {}
    with open("/etc/dyndns.conf", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ValueError(f"Ungültige Zeile in /etc/dyndns.conf: {line}")

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key or not value:
                raise ValueError(f"Fehlender Schlüssel oder Wert in /etc/dyndns.conf: {line}")

            creds[key] = value

    missing_keys = {"USERNAME", "PASSWORD"} - creds.keys()
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise KeyError(f"Fehlende Einträge in /etc/dyndns.conf: {missing}")

    return creds

creds = load_credentials()
USERNAME = creds["USERNAME"]
PASSWORD = creds["PASSWORD"]

error_occurred = False
log_file = None


def setup_logger():
    global log_file

    os.makedirs(LOG_DIR, exist_ok=True)

    date_str = datetime.now().strftime("%y_%m_%d")
    normal_log = os.path.join(LOG_DIR, f"{date_str}.log")
    error_log = os.path.join(LOG_DIR, f"{date_str}_error.log")

    log_file = error_log if os.path.exists(error_log) else normal_log

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        filemode="a"
    )


def get_ip(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            ip = response.read().decode().strip()
            return ip if ip else None
    except Exception as e:
        logging.warning("IP-Abruf fehlgeschlagen für %s: %s", url, e)
        return None


def get_public_ipv4() -> str | None:
    return get_ip("https://api.ipify.org")


def get_public_ipv6() -> str | None:
    return get_ip("https://api6.ipify.org")


def get_domain_ipv4(domain: str) -> str | None:
    try:
        return socket.gethostbyname(domain)
    except Exception as e:
        logging.warning("IPv4-DNS-Auflösung fehlgeschlagen für %s: %s", domain, e)
        return None


def get_domain_ipv6(domain: str) -> str | None:
    try:
        info = socket.getaddrinfo(domain, None, socket.AF_INET6)
        for entry in info:
            sockaddr = entry[4]
            if sockaddr and len(sockaddr) > 0:
                return sockaddr[0]
        return None
    except Exception as e:
        logging.warning("IPv6-DNS-Auflösung fehlgeschlagen für %s: %s", domain, e)
        return None


def update_strato_ddns(ipv4: str | None, ipv6: str | None):
    global error_occurred

    if not ipv4 and not ipv6:
        logging.error("Weder IPv4 noch IPv6 verfügbar. DynDNS-Update wird nicht ausgeführt.")
        error_occurred = True
        return

    myip_parts = []
    if ipv4:
        myip_parts.append(ipv4)
    if ipv6:
        myip_parts.append(ipv6)

    myip_value = ",".join(myip_parts)

    base_url = "https://dyndns.strato.com/nic/update"
    query = urllib.parse.urlencode({
        "hostname": DOMAIN,
        "myip": myip_value
    })
    url = f"{base_url}?{query}"
    auth = base64.b64encode(f"{USERNAME}:{PASSWORD}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_text = response.read().decode().strip()
            if response.status != 200:
                logging.error("HTTP-Status ungleich 200: %s", response.status)
                error_occurred = True

            lowered = response_text.lower()

            if lowered.startswith("good") or lowered.startswith("nochg"):
                logging.info("Strato DynDNS-Antwort: %s", response_text)
            else:
                error_occurred = True
                logging.error("Fehlerhafte DynDNS-Antwort: %s", response_text)

    except urllib.error.HTTPError as e:
        logging.error("HTTP-Fehler beim DynDNS-Update: %s", e)
        try:
            body = e.read().decode().strip()
            if body:
                logging.error("HTTP-Fehlertext: %s", body)
        except Exception:
            pass
        error_occurred = True

    except Exception as e:
        logging.error("Fehler beim DynDNS-Update: %s", e)
        error_occurred = True


def finalize_log():
    global log_file

    if not error_occurred:
        return

    date_str = datetime.now().strftime("%y_%m_%d")
    normal_log = os.path.join(LOG_DIR, f"{date_str}.log")
    error_log = os.path.join(LOG_DIR, f"{date_str}_error.log")

    for handler in logging.getLogger().handlers:
        handler.flush()
        handler.close()

    logging.getLogger().handlers.clear()

    if os.path.exists(normal_log) and not os.path.exists(error_log):
        os.rename(normal_log, error_log)


def main():
    global error_occurred

    ipv4 = get_public_ipv4()
    ipv6 = get_public_ipv6()

    dns_ipv4 = get_domain_ipv4(DOMAIN)
    dns_ipv6 = get_domain_ipv6(DOMAIN)

    logging.info("Öffentliche IPv4: %s", ipv4 if ipv4 else "nicht verfügbar")
    logging.info("Öffentliche IPv6: %s", ipv6 if ipv6 else "nicht verfügbar")
    logging.info("Domain IPv4: %s", dns_ipv4 if dns_ipv4 else "nicht verfügbar")
    logging.info("Domain IPv6: %s", dns_ipv6 if dns_ipv6 else "nicht verfügbar")

    ipv4_differs = ipv4 and (ipv4 != dns_ipv4)
    ipv6_differs = ipv6 and (ipv6 != dns_ipv6)

    if ipv4_differs or ipv6_differs:
        logging.warning("IP-Abweichung erkannt. DynDNS-Update wird gestartet.")
        update_strato_ddns(ipv4, ipv6)
    else:
        logging.info("IPv4/IPv6 identisch. Kein Update nötig.")


if __name__ == "__main__":
    setup_logger()
    try:
        main()
    except Exception as e:
        error_occurred = True
        logging.exception("Unerwarteter Fehler im Hauptlauf: %s", e)
    finally:
        finalize_log()
