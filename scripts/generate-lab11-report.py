#!/usr/bin/env python3
"""Create a compact Markdown health and log-ingestion report for LAB-11."""
import argparse
import datetime
from pathlib import Path
import requests


def query(base_url, body):
    response = requests.post(f"{base_url}/novashop-*/_search", json=body, timeout=10)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Generate a NovaShop LAB-11 report")
    parser.add_argument("--es-url", default="http://localhost:9200")
    parser.add_argument("--output", default="reports/lab-11")
    args = parser.parse_args()

    base_url = args.es_url.rstrip("/")
    health = requests.get(f"{base_url}/_cluster/health", timeout=10).json()
    indices = requests.get(f"{base_url}/_cat/indices/novashop-*?format=json", timeout=10).json()

    total = query(base_url, {"size": 0, "query": {"match_all": {}}, "aggs": {
        "sources": {"terms": {"field": "log_source", "size": 20}},
        "levels": {"terms": {"field": "level", "size": 20}},
        "services": {"terms": {"field": "service", "size": 20}}
    }})
    recent_errors = query(base_url, {"size": 10, "sort": [{"@timestamp": "desc"}], "query": {
        "bool": {"filter": [{"term": {"level": "ERROR"}}]}
    }, "_source": ["@timestamp", "service", "log_source", "message", "trace_id", "http_status"]})

    def buckets(name):
        return total["aggregations"][name]["buckets"]

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# NovaShop LAB-11 — Log Sağlık Raporu", "",
        f"Üretim zamanı: {timestamp}", "",
        "## Elasticsearch", "",
        f"- Cluster: `{health['cluster_name']}`", f"- Durum: `{health['status']}`", f"- Düğüm sayısı: `{health['number_of_nodes']}`", "",
        "## İndeksler", "", "| İndeks | Doküman | Boyut |", "|---|---:|---:|"
    ]
    for index in indices:
        lines.append(f"| `{index['index']}` | {index.get('docs.count', '0')} | {index.get('store.size', '-')} |")

    for title, key in [("Kaynağa göre loglar", "sources"), ("Seviyeye göre loglar", "levels"), ("Servise göre loglar", "services")]:
        lines += ["", f"## {title}", "", "| Değer | Adet |", "|---|---:|"]
        lines += [f"| `{item['key']}` | {item['doc_count']} |" for item in buckets(key)]

    lines += ["", "## Son hata kayıtları", ""]
    if not recent_errors["hits"]["hits"]:
        lines.append("Hata kaydı yok.")
    else:
        lines += ["| Zaman | Servis | Kaynak | HTTP | Mesaj | Trace ID |", "|---|---|---|---:|---|---|"]
        for hit in recent_errors["hits"]["hits"]:
            doc = hit["_source"]
            message = str(doc.get("message", "")).replace("|", "\\|")
            lines.append(f"| {doc.get('@timestamp', '-')} | {doc.get('service', '-')} | {doc.get('log_source', '-')} | {doc.get('http_status', '-')} | {message} | `{doc.get('trace_id', '-')}` |")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"lab-11-report-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output_file)


if __name__ == "__main__":
    main()
