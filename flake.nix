{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    pre-commit-hooks.url = "github:cachix/pre-commit-hooks.nix";
  };

  outputs =
    inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        ./module.nix
        inputs.pre-commit-hooks.flakeModule
      ];

      systems = inputs.nixpkgs.lib.systems.flakeExposed;

      perSystem =
        {
          config,
          pkgs,
          self',
          ...
        }:
        {
          devShells.default = pkgs.mkShell {
            inputsFrom = [
              self'.packages.default
              config.pre-commit.devShell
            ];
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
                ]
              ))
            ];
          };

          packages.default = import ./. { inherit pkgs; };

          apps.default = {
            type = "app";
            program = "${self'.packages.default}/bin/fetch-podcasts";
          };

          formatter = pkgs.nixfmt-tree;
          pre-commit.settings = {
            default_stages = [ "pre-push" ];
            hooks.nixfmt.enable = true;
            hooks.deadnix.enable = true;
            hooks.statix.enable = true;
            hooks.ruff.enable = true;
            hooks.ruff-format.enable = true;
          };
        };
    };
}
