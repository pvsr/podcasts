{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs =
    inputs:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        ./module.nix
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
            inputsFrom = [ self'.packages.default ];
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
        };
    };
}
