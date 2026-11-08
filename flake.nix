{
  description = "demo_http_mcp — HTTP MCP server (Python/uv) + React frontend (Vite/npm)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];

      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          name = "demo-http-mcp";

          packages = [
            # --- Backend: Python 3.13, per pyproject requires-python >=3.13,<3.14 ---
            pkgs.python313
            pkgs.uv

            # --- Frontend: Vite 8 needs Node >=20.19; @types/node is ^24 ---
            pkgs.nodejs_24

            # --- Shared tooling ---
            # git: .githooks/pre-push, and the uv git source for
            # microsoft-python-type-stubs in backend/pyproject.toml
            pkgs.git
            # sqlite CLI: inspect the agent memory DB written by app/agen_memory.py
            pkgs.sqlite
            # TLS roots for uv / npm network fetches
            pkgs.cacert
          ];

          env = {
            # Pin uv to the Nix interpreter instead of letting it download its own,
            # so every toolchain dependency comes from this flake.
            UV_PYTHON = pkgs.python313.interpreter;
            UV_PYTHON_DOWNLOADS = "never";

            # Default model backend for the pydantic-ai agent (app/app.py).
            OLLAMA_BASE_URL = "http://localhost:11434/v1";
          };

          shellHook = ''
            # Only take the bundled CA roots if nothing is configured already,
            # so a system/corporate cert store keeps working.
            if [ -z "''${SSL_CERT_FILE:-}" ]; then
              export SSL_CERT_FILE="${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
            fi
            export NODE_EXTRA_CA_CERTS="''${NODE_EXTRA_CA_CERTS:-$SSL_CERT_FILE}"

            # Keep the repo's pre-push hook wired up (was in .envrc).
            if [ -d .githooks ]; then
              chmod +x .githooks/pre-push 2>/dev/null || true
              git config core.hooksPath .githooks
            fi

            echo "demo_http_mcp dev shell"
            echo "  python $(python3 --version 2>&1 | cut -d' ' -f2)  uv $(uv --version | cut -d' ' -f2)  node $(node --version)"
            echo "  backend:  cd backend && uv sync && uv run run-app-local"
            echo "  frontend: cd frontend && npm install && npm run dev"
          '';
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
