{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }:
    let out = system:
      let
        pkgs = nixpkgs.legacyPackages."${system}";
        devEnv = pkgs.poetry2nix.mkPoetryEnv {
          projectDir = ./.;
          preferWheels = true;
        };
      in
      rec {

        devShell = pkgs.mkShell {
          buildInputs = [
            pkgs.python3Packages.poetry
            pkgs.sqlite
            devEnv
          ];
        };

        packages = {
          fetch-podcasts = pkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            preferWheels = true;
          };
        };

        defaultPackage = packages.fetch-podcasts;

        apps = {
          fetch-podcasts = utils.lib.mkApp {
            drv = packages.fetch-podcasts;
            exePath = "/bin/fetch-podcasts";
          };
        };

        defaultApp = apps.fetch-podcasts;
      };
    in with utils.lib; eachSystem defaultSystems out;

}
