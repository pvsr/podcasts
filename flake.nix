{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
    pre-commit-hooks.url = "github:cachix/pre-commit-hooks.nix";
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
      pre-commit-hooks,
    }:
    let
      out =
        system:
        let
          pkgs = nixpkgs.legacyPackages."${system}";
        in
        rec {
          devShells.default = pkgs.mkShell {
            inherit (self.checks.${system}.pre-commit-check) shellHook;
            inputsFrom = [ packages.default ];
            buildInputs = with pkgs; [
              sqlite
              ruff
              (python3.withPackages (
                ps: with ps; [
                  mypy
                  types-requests
                  types-pyyaml
                  gunicorn

                  pylsp-mypy
                  ruff-lsp
                ]
              ))
            ];
          };

          packages.default = import ./. { inherit pkgs; };

          apps.default = utils.lib.mkApp {
            drv = packages.default;
            exePath = "/bin/fetch-podcasts";
          };

          checks = {
            pre-commit-check = pre-commit-hooks.lib.${system}.run {
              src = ./.;
              hooks = {
                alejandra.enable = true;
                deadnix.enable = true;
                statix.enable = true;

                black.enable = true;
                ruff.enable = true;
              };
            };
          };

          formatter = pkgs.nixfmt-rfc-style;
        };
    in
    utils.lib.eachDefaultSystem out
    // {
      nixosModules.default = import ./module.nix;
    };
}
