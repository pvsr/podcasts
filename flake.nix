{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
    nix-gleam.url = "github:arnarg/nix-gleam";
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
      nix-gleam,
    }:
    let
      out =
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [
              nix-gleam.overlays.default
            ];
          };
        in
        rec {
          devShells.default = pkgs.mkShell {
            packages = with pkgs; [
              litecli
              erlang
              rebar3
            ];
          };

          packages.default = pkgs.buildGleamApplication {
            src = ./.;
          };

          apps.default = utils.lib.mkApp {
            drv = packages.default;
          };

          formatter = pkgs.nixfmt-rfc-style;
        };
    in
    utils.lib.eachDefaultSystem out;
}
