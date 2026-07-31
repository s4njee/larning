#!/usr/bin/env python3
"""Build every study-guide HTML page into the shared html/ directory."""

from pathlib import Path
import subprocess
import sys

from build_caddy_html import CSS, JS
from build_guide import PAGE, apply_accent, auto_accent, build, esc_attr, rewrite_local_markdown_links, transform


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
    ("ADVANCED_RUST_STUDY_GUIDE.md", "html/advanced-rust-study-guide.html", {"accent": "#f74c00"}),
    ("TYPESCRIPT_STUDY_GUIDE.md", "html/typescript-study-guide.html", {"accent": "#3178c6", "brand": "TS"}),
    ("COMPILER_INTERNALS_STUDY_GUIDE.md", "html/compiler-internals-study-guide.html", {"auto": True}),
    ("SCALA_STUDY_GUIDE.md", "html/scala-study-guide.html", {"accent": "#dc322f", "brand": "Scala"}),
    ("WEBASSEMBLY_STUDY_GUIDE.md", "html/webassembly-study-guide.html", {"accent": "#654ff0", "brand": "Wasm"}),
    ("SWIFT_STUDY_GUIDE.md", "html/swift-study-guide.html", {"accent": "#f05138", "brand": "Swift"}),
    ("IOS_DEVELOPMENT_STUDY_GUIDE.md", "html/ios-development-study-guide.html", {"accent": "#f05138", "brand": "iOS"}),
    ("CB8_IOS_STUDY_GUIDE.md", "html/cb8-ios-study-guide.html", {"accent": "#f05138", "brand": "CB8"}),
    ("CB8_ANDROID_STUDY_GUIDE.md", "html/cb8-android-study-guide.html", {"accent": "#3ddc84", "brand": "CB8"}),
    ("DJANGO_STUDY_GUIDE.md", "html/django-study-guide.html", {"accent": "#ffd43b"}),
    ("ELECTRON_STUDY_GUIDE.md", "html/electron-study-guide.html", {"auto": True}),
    ("NEXTJS_STUDY_GUIDE.md", "html/nextjs-study-guide.html", {"auto": True}),
    ("QT_STUDY_GUIDE.md", "html/qt-study-guide.html", {"auto": True}),
    ("SVELTEKIT_STUDY_GUIDE.md", "html/sveltekit-study-guide.html", {"auto": True}),
    ("VUE_STUDY_GUIDE.md", "html/vue-study-guide.html", {"accent": "#42b883"}),
    ("WEBGL_OPENGL_STUDY_GUIDE.md", "html/webgl-opengl-study-guide.html", {"auto": True}),
    ("WEBGPU_STUDY_GUIDE.md", "html/webgpu-study-guide.html", {"auto": True}),
    ("WEBSOCKETS_STUDY_GUIDE.md", "html/websockets-study-guide.html", {"auto": True}),
    ("BLENDER_STUDY_GUIDE.md", "html/blender-study-guide.html", {"accent": "#ea7600"}),
    ("BLENDER_ANIMATION_STUDY_GUIDE.md", "html/blender-animation-study-guide.html", {"accent": "#ea7600", "brand": "Anim"}),
    ("UNREAL_ENGINE_STUDY_GUIDE.md", "html/unreal-engine-study-guide.html", {"accent": "#1ea7e1", "brand": "UE"}),
    ("ANSIBLE_STUDY_GUIDE.md", "html/ansible-study-guide.html", {"auto": True}),
    ("AWS_FUNDAMENTALS_STUDY_GUIDE.md", "html/aws-fundamentals-study-guide.html", {"accent": "#ff9900", "brand": "AWS"}),
    ("AZURE_FOR_AWS_SOLUTIONS_ARCHITECT.md", "html/azure-for-aws-solutions-architect.html", {"auto": True}),
    ("GCP_FOR_AWS_SOLUTIONS_ARCHITECT.md", "html/gcp-for-aws-solutions-architect.html", {"auto": True}),
    ("CLOUDFLARE_STUDY_GUIDE.md", "html/cloudflare-study-guide.html", {"auto": True}),
    ("DOCKER_STUDY_GUIDE.md", "html/docker-study-guide.html", {"accent": "#2496ed"}),
    ("GITHUB_ACTIONS_STUDY_GUIDE.md", "html/github-actions-study-guide.html", {"auto": True}),
    ("OBSERVABILITY_STUDY_GUIDE.md", "html/observability-study-guide.html", {"auto": True}),
    ("TESTING_STUDY_GUIDE.md", "html/testing-study-guide.html", {"auto": True}),
    ("TERRAFORM_STUDY_GUIDE.md", "html/terraform-study-guide.html", {"auto": True}),
    ("k8s/ADVANCED_KUBERNETES_STUDY_GUIDE.md", "html/advanced-kubernetes-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("k8s/DOCKER_KUBERNETES_NETWORKING_STUDY_GUIDE.md", "html/docker-kubernetes-networking-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("k8s/KUBERNETES_SECURITY_STUDY_GUIDE.md", "html/kubernetes-security-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("k8s/KUBERNETES_STUDY_GUIDE.md", "html/kubernetes-study-guide.html", {"accent": "#326ce5", "brand": "K8s"}),
    ("ADVANCED_LINUX_STUDY_GUIDE.md", "html/advanced-linux-study-guide.html", {"auto": True}),
    ("LINUX_FUNDAMENTALS_STUDY_GUIDE.md", "html/linux-fundamentals-study-guide.html", {"auto": True}),
    ("LINUX_NETWORKING_STUDY_GUIDE.md", "html/linux-networking-study-guide.html", {"auto": True}),
    ("ESP32_STUDY_GUIDE.md", "html/esp32-study-guide.html", {"auto": True}),
    ("RASPBERRY_PI_STUDY_GUIDE.md", "html/raspberry-pi-study-guide.html", {"accent": "#c51a4a", "brand": "RPi"}),
    ("SYSTEMD_STUDY_GUIDE.md", "html/systemd-study-guide.html", {"auto": True, "brand": "sd"}),
    ("GIT_STUDY_GUIDE.md", "html/git-study-guide.html", {"auto": True}),
    ("VIM_STUDY_GUIDE.md", "html/vim-study-guide.html", {"auto": True}),
    ("DATA_ENGINEERING_STUDY_GUIDE.md", "html/data-engineering-study-guide.html", {"auto": True}),
    ("DATABASE_INTERNALS_STUDY_GUIDE.md", "html/database-internals-study-guide.html", {"auto": True}),
    ("POSTGRES.md", "html/postgres.html", {"accent": "#336791"}),
    ("ADVANCED_POSTGRES.md", "html/advanced-postgres.html", {"accent": "#336791"}),
    ("POSTGRES_EXTENSIONS.md", "html/postgres-extensions.html", {"accent": "#336791"}),
    ("REDIS_STUDY_GUIDE.md", "html/redis-study-guide.html", {"accent": "#ff4438"}),
    ("SQLITE_STUDY_GUIDE.md", "html/sqlite-study-guide.html", {"auto": True}),
    ("KAFKA_STUDY_GUIDE.md", "html/kafka-study-guide.html", {"auto": True}),
    ("AI_AGENTS_STUDY_GUIDE.md", "html/ai-agents-study-guide.html", {"auto": True}),
    ("AUTH_STUDY_GUIDE.md", "html/auth-study-guide.html", {"auto": True}),
    ("CRYPTO_FUNDAMENTALS.md", "html/crypto-fundamentals.html", {"auto": True}),
    ("DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md", "html/distributed-systems-study-guide.html", {"auto": True}),
    ("DISTRIBUTED_ALGORITHMS_STUDY_GUIDE.md", "html/distributed-algorithms-study-guide.html", {"auto": True}),
    ("DURABLE_EXECUTION_STUDY_GUIDE.md", "html/durable-execution-study-guide.html", {"auto": True}),
    ("QUANTUM_COMPUTING_STUDY_GUIDE.md", "html/quantum-computing-study-guide.html", {"auto": True}),
    ("KALI_LINUX_STUDY_GUIDE.md", "html/kali-linux-study-guide.html", {"auto": True}),
    ("WEB_LLM_SECURITY_STUDY_GUIDE.md", "html/web-llm-security-study-guide.html", {"auto": True}),
    ("LLM_APP_DEV_STUDY_GUIDE.md", "html/llm-app-dev-study-guide.html", {"auto": True}),
    ("RAG_STUDY_GUIDE.md", "html/rag-study-guide.html", {"auto": True}),
    ("NETWORKING_FUNDAMENTALS.md", "html/networking-fundamentals.html", {"auto": True}),
    ("EBPF_STUDY_GUIDE.md", "html/ebpf-study-guide.html", {"auto": True}),
    ("CUDA_STUDY_GUIDE.md", "html/cuda-study-guide.html", {"accent": "#76b900", "brand": "CUDA"}),
    ("ENTERPRISE_API_STUDY_GUIDE.md", "html/enterprise-api-study-guide.html", {"auto": True}),
    ("API_DESIGN_STUDY_GUIDE.md", "html/api-design-study-guide.html", {"auto": True}),
    ("README.md", "html/readme.html", {"title": "Study Guides", "brand": "SG", "auto": True}),
    ("TOPICS.md", "html/topics.html", {"title": "Study Guide Topics", "brand": "SG", "auto": True}),
    ("ToDo.md", "html/todo.html", {"title": "Study Guide Conversion ToDo", "brand": "TODO", "auto": True}),
    ("REMAINING.md", "html/remaining.html", {"title": "Remaining Topics in 2026", "brand": "TODO", "auto": True}),
]

CATEGORIES = [
    ("Languages and runtimes", [
        "advanced-go-study-guide.html", "advanced-nodejs-study-guide.html",
        "advanced-python-study-guide.html", "asyncio-study-guide.html",
        "cpp26-study-guide.html", "dotnet-for-python-devs.html",
        "golang-for-python-devs.html", "python-concurrency.html",
        "python-vs-nodejs-async-study-guide.html", "rust-for-python-devs.html",
        "advanced-rust-study-guide.html",
        "typescript-study-guide.html", "swift-study-guide.html",
        "scala-study-guide.html", "webassembly-study-guide.html",
        "compiler-internals-study-guide.html",
    ]),
    ("Web and frontend", [
        "django-study-guide.html", "electron-study-guide.html",
        "nextjs-study-guide.html", "qt-study-guide.html",
        "sveltekit-study-guide.html", "vue-study-guide.html",
        "webgl-opengl-study-guide.html", "webgpu-study-guide.html", "websockets-study-guide.html",
        "ios-development-study-guide.html", "cb8-ios-study-guide.html",
        "cb8-android-study-guide.html",
    ]),
    ("Creative and 3D", [
        "blender-study-guide.html",
        "blender-animation-study-guide.html",
        "unreal-engine-study-guide.html",
    ]),
    ("Infra, cloud, and ops", [
        "ansible-study-guide.html", "aws-fundamentals-study-guide.html",
        "azure-for-aws-solutions-architect.html",
        "gcp-for-aws-solutions-architect.html",
        "cloudflare-study-guide.html", "docker-study-guide.html",
        "github-actions-study-guide.html", "observability-study-guide.html",
        "terraform-study-guide.html", "advanced-kubernetes-study-guide.html",
        "docker-kubernetes-networking-study-guide.html",
        "kubernetes-security-study-guide.html", "kubernetes-study-guide.html",
        "ebpf-study-guide.html",
    ]),
    ("Systems, OS, and hardware", [
        "advanced-linux-study-guide.html", "linux-fundamentals-study-guide.html",
        "linux-networking-study-guide.html", "systemd-study-guide.html",
        "esp32-study-guide.html", "raspberry-pi-study-guide.html",
        "cuda-study-guide.html",
        "git-study-guide.html", "vim-study-guide.html",
    ]),
    ("Data and messaging", [
        "data-engineering-study-guide.html", "database-internals-study-guide.html",
        "postgres.html",
        "advanced-postgres.html", "postgres-extensions.html",
        "redis-study-guide.html", "sqlite-study-guide.html",
        "kafka-study-guide.html",
    ]),
    ("Architecture, security, and AI", [
        "ai-agents-study-guide.html", "auth-study-guide.html",
        "crypto-fundamentals.html", "distributed-systems-study-guide.html",
        "distributed-algorithms-study-guide.html", "durable-execution-study-guide.html",
        "quantum-computing-study-guide.html",
        "enterprise-api-study-guide.html",
        "kali-linux-study-guide.html", "llm-app-dev-study-guide.html",
        "rag-study-guide.html", "api-design-study-guide.html",
        "web-llm-security-study-guide.html",
        "networking-fundamentals.html", "testing-study-guide.html",
    ]),
    ("Bespoke and repo pages", [
        "caddy-study-guide.html", "nginx-study-guide.html", "readme.html",
        "topics.html", "todo.html", "remaining.html",
    ]),
]


def guide_link_rewrites():
    rewrites = {}
    for src, out, _ in GUIDES:
        target = Path(out).name
        src_path = Path(src).as_posix()
        keys = {
            src_path,
            f"./{src_path}",
            Path(src_path).name,
        }
        for key in keys:
            rewrites[key] = target
    bespoke = {
        "CADDY_STUDY_GUIDE.md": "caddy-study-guide.html",
        "NGINX_STUDY_GUIDE.md": "nginx-study-guide.html",
    }
    for src, target in bespoke.items():
        rewrites[src] = target
        rewrites[f"./{src}"] = target
    return rewrites


def rewrite_site_links(link_rewrites):
    for path in Path("html").glob("*.html"):
        original = path.read_text(encoding="utf-8")
        rewritten = rewrite_local_markdown_links(original, link_rewrites)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")


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

    link_rewrites = guide_link_rewrites()
    for src, out, opts in GUIDES:
        build(src, out=out, link_rewrites=link_rewrites, **opts)
        print(f"wrote {out}")

    build_index()
    rewrite_site_links(link_rewrites)


if __name__ == "__main__":
    main()
