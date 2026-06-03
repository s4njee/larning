#!/usr/bin/env python3
"""Build every study-guide HTML page into the shared html/ directory."""

from pathlib import Path
import subprocess
import sys

from build_caddy_html import CSS, JS
from build_guide import PAGE, apply_accent, auto_accent, build, esc_attr, transform


GUIDES = [
    ("ADVANCED_GO_STUDY_GUIDE.md", "html/advanced-go-study-guide.html", {"accent": "#00add8"}),
    ("ADVANCED_NODEJS_STUDY_GUIDE.md", "html/advanced-nodejs-study-guide.html", {"auto": True}),
    ("ADVANCED_PYTHON_STUDY_GUIDE.md", "html/advanced-python-study-guide.html", {"accent": "#ffd43b"}),
    ("ASYNCIO_STUDY_GUIDE.md", "html/asyncio-study-guide.html", {"accent": "#ffd43b"}),
    ("CPP26_STUDY_GUIDE.md", "html/cpp26-study-guide.html", {"auto": True}),
    ("DOTNET_FOR_PYTHON_DEVS.md", "html/dotnet-for-python-devs.html", {"auto": True}),
    ("GOLANG_FOR_PYTHON_DEVS.md", "html/golang-for-python-devs.html", {"accent": "#00add8"}),
    ("PYTHON_CONCURRENCY.md", "html/python-concurrency.html", {"accent": "#ffd43b"}),
    ("PYTHON_VS_NODEJS_ASYNC_STUDY_GUIDE.md", "html/python-vs-nodejs-async-study-guide.html", {"accent": "#ffd43b"}),
    ("RUST_FOR_PYTHON_DEVS.md", "html/rust-for-python-devs.html", {"accent": "#f74c00"}),
    ("TYPESCRIPT_STUDY_GUIDE.md", "html/typescript-study-guide.html", {"accent": "#3178c6", "brand": "TS"}),
    ("DJANGO_STUDY_GUIDE.md", "html/django-study-guide.html", {"accent": "#ffd43b"}),
    ("ELECTRON_STUDY_GUIDE.md", "html/electron-study-guide.html", {"auto": True}),
    ("NEXTJS_STUDY_GUIDE.md", "html/nextjs-study-guide.html", {"auto": True}),
    ("QT_STUDY_GUIDE.md", "html/qt-study-guide.html", {"auto": True}),
    ("SVELTEKIT_STUDY_GUIDE.md", "html/sveltekit-study-guide.html", {"auto": True}),
    ("VUE_STUDY_GUIDE.md", "html/vue-study-guide.html", {"accent": "#42b883"}),
    ("WEBSOCKETS_STUDY_GUIDE.md", "html/websockets-study-guide.html", {"auto": True}),
    ("ANSIBLE_STUDY_GUIDE.md", "html/ansible-study-guide.html", {"auto": True}),
    ("AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md", "html/azure-for-aws-solutions-architect.html", {"auto": True}),
    ("CLOUDFLARE_STUDY_GUIDE.md", "html/cloudflare-study-guide.html", {"auto": True}),
    ("DOCKER_STUDY_GUIDE.md", "html/docker-study-guide.html", {"accent": "#2496ed"}),
    ("GITHUB_ACTIONS_STUDY_GUIDE.md", "html/github-actions-study-guide.html", {"auto": True}),
    ("OBSERVABILITY_STUDY_GUIDE.md", "html/observability-study-guide.html", {"auto": True}),
    ("TERRAFORM_STUDY_GUIDE.md", "html/terraform-study-guide.html", {"auto": True}),
    ("k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md", "html/advanced-kubernetes-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md", "html/docker-kubernetes-networking-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md", "html/kubernetes-security-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("k8s/KUBERNETES_STUDY_GUIDE.md", "html/kubernetes-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("ADVANCED_LINUX_STUDY_GUIDE.md", "html/advanced-linux-study-guide.html", {"auto": True}),
    ("LINUX_FUNDAMENTALS_STUDY_GUIDE.md", "html/linux-fundamentals-study-guide.html", {"auto": True}),
    ("ESP32_STUDY_GUIDE.md", "html/esp32-study-guide.html", {"auto": True}),
    ("GIT_STUDY_GUIDE.md", "html/git-study-guide.html", {"auto": True}),
    ("VIM_STUDY_GUIDE.md", "html/vim-study-guide.html", {"auto": True}),
    ("DATA_ENGINEERING_STUDY_GUIDE.md", "html/data-engineering-study-guide.html", {"auto": True}),
    ("POSTGRES.md", "html/postgres.html", {"accent": "#336791"}),
    ("POSTGRES_STUDY_GUIDE.md", "html/postgres-study-guide.html", {"accent": "#336791"}),
    ("REDIS_STUDY_GUIDE.md", "html/redis-study-guide.html", {"accent": "#ff4438"}),
    ("AI_AGENTS_STUDY_GUIDE.md", "html/ai-agents-study-guide.html", {"auto": True}),
    ("AUTH_STUDY_GUIDE.md", "html/auth-study-guide.html", {"auto": True}),
    ("CRYPTO_FUNDAMENTALS.md", "html/crypto-fundamentals.html", {"auto": True}),
    ("DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md", "html/distributed-systems-study-guide.html", {"auto": True}),
    ("KALI_LINUX_STUDY_GUIDE.md", "html/kali-linux-study-guide.html", {"auto": True}),
    ("LLM_APP_DEV_STUDY_GUIDE.md", "html/llm-app-dev-study-guide.html", {"auto": True}),
    ("NETWORKING_FUNDAMENTALS.md", "html/networking-fundamentals.html", {"auto": True}),
    ("EBPF_STUDY_GUIDE.md", "html/ebpf-study-guide.html", {"auto": True}),
    ("README.md", "html/readme.html", {"title": "Study Guides", "brand": "SG", "auto": True}),
    ("TOPICS.md", "html/topics.html", {"title": "Study Guide Topics", "brand": "SG", "auto": True}),
    ("ToDo.md", "html/todo.html", {"title": "Study Guide Conversion ToDo", "brand": "TODO", "auto": True}),
]

CATEGORIES = [
    ("Languages and runtimes", [
        "advanced-go-study-guide.html", "advanced-nodejs-study-guide.html",
        "advanced-python-study-guide.html", "asyncio-study-guide.html",
        "cpp26-study-guide.html", "dotnet-for-python-devs.html",
        "golang-for-python-devs.html", "python-concurrency.html",
        "python-vs-nodejs-async-study-guide.html", "rust-for-python-devs.html",
        "typescript-study-guide.html",
    ]),
    ("Web and frontend", [
        "django-study-guide.html", "electron-study-guide.html",
        "nextjs-study-guide.html", "qt-study-guide.html",
        "sveltekit-study-guide.html", "vue-study-guide.html",
        "websockets-study-guide.html",
    ]),
    ("Infra, cloud, and ops", [
        "ansible-study-guide.html", "azure-for-aws-solutions-architect.html",
        "cloudflare-study-guide.html", "docker-study-guide.html",
        "github-actions-study-guide.html", "observability-study-guide.html",
        "terraform-study-guide.html", "advanced-kubernetes-study-guide.html",
        "docker-kubernetes-networking-study-guide.html",
        "kubernetes-security-study-guide.html", "kubernetes-study-guide.html",
        "ebpf-study-guide.html",
    ]),
    ("Systems, OS, and hardware", [
        "advanced-linux-study-guide.html", "linux-fundamentals-study-guide.html",
        "esp32-study-guide.html", "git-study-guide.html", "vim-study-guide.html",
    ]),
    ("Data and messaging", [
        "data-engineering-study-guide.html", "postgres.html",
        "postgres-study-guide.html", "redis-study-guide.html",
    ]),
    ("Architecture, security, and AI", [
        "ai-agents-study-guide.html", "auth-study-guide.html",
        "crypto-fundamentals.html", "distributed-systems-study-guide.html",
        "kali-linux-study-guide.html", "llm-app-dev-study-guide.html",
        "networking-fundamentals.html",
    ]),
    ("Bespoke and repo pages", [
        "caddy-study-guide.html", "nginx-study-guide.html", "readme.html",
        "topics.html", "todo.html",
    ]),
]


def title_for(path):
    text = Path("html", path).read_text(encoding="utf-8")
    start = text.find("<title>")
    end = text.find("</title>", start)
    if start == -1 or end == -1:
        return path.replace("-", " ").removesuffix(".html").title()
    return text[start + len("<title>"):end].replace(" - Interactive", "").replace(" - interactive", "")


def build_index():
    lines = [
        "# Study Guides Index",
        "",
        "A local index of the generated interactive study guides.",
        "",
    ]
    for heading, pages in CATEGORIES:
        lines.append(f"## {heading}")
        lines.append("")
        for page in pages:
            if Path("html", page).exists():
                lines.append(f"- [{title_for(page)}]({page})")
        lines.append("")

    toc_html, body = transform("\n".join(lines))
    accent, accent2 = auto_accent("Study Guides Index")
    css = apply_accent(CSS, accent, accent2)
    title = "Study Guides Index"
    page = (PAGE
            .replace("__CSS__", css)
            .replace("__JS__", JS)
            .replace("__TOC__", toc_html)
            .replace("__BODY__", body)
            .replace("__TITLE__", esc_attr(title) + " - Interactive")
            .replace("__DESC__", esc_attr("A local index of generated interactive study guides."))
            .replace("__BRAND__", "SG")
            .replace("__NAME__", esc_attr(title)))
    Path("html/index.html").write_text(page, encoding="utf-8")
    print("wrote html/index.html")


def main():
    Path("html").mkdir(exist_ok=True)
    for bespoke in ("build_caddy_html.py", "build_nginx_html.py"):
        subprocess.run([sys.executable, bespoke], check=True)

    for src, out, opts in GUIDES:
        build(src, out=out, **opts)
        print(f"wrote {out}")

    build_index()


if __name__ == "__main__":
    main()
