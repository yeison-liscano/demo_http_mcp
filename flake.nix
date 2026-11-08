{
  description = "demo_http_mcp — MCP server over HTTP and stdio (Python/uv)";

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

            # --- Node: npx-based MCP tooling (e.g. the auth0 server in .mcp.json) ---
            pkgs.nodejs_24

            # --- Shared tooling ---
            # git: .githooks/pre-push, and the uv git source for
            # microsoft-python-type-stubs in backend/pyproject.toml
            pkgs.git
            # TLS roots for uv / npm network fetches
            pkgs.cacert
          ];

          env = {
            # Pin uv to the Nix interpreter instead of letting it download its own,
            # so every toolchain dependency comes from this flake.
            UV_PYTHON = pkgs.python313.interpreter;
            UV_PYTHON_DOWNLOADS = "never";
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
            echo "  http:  cd backend && uv sync && uv run run-app-local"
            echo "  stdio: cd backend && uv run run-stdio"
          '';
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
