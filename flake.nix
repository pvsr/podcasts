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

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.python3Packages.poetry
            pkgs.sqlite
            devEnv
          ];
        };

        packages.default = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          preferWheels = true;
        };

        apps.default = utils.lib.mkApp {
          drv = packages.podcasts;
          exePath = "/bin/fetch-podcasts";
        };

        nixosModules.default = { config, lib, pkgs, ... }:
          let
            cfg = config.services.podcasts;
            podcasts = self.outputs.packages."${pkgs.system}".podcasts;
            penv = podcasts.dependencyEnv;
            fetch-podcasts = "${podcasts}/bin/fetch-podcasts";
            stateDirectory = "/var/lib/podcasts/";
            commonServiceConfig = {
              DynamicUser = true;
              User = "podcasts";
              Group = "podcasts";
              StateDirectory = "podcasts";
              WorkingDirectory = cfg.podcastDir;
              ProtectHome = "tmpfs";
            };
          in
          {
            options = {
              services.podcasts = with lib; {
                enableFetch = mkEnableOption "fetch-podcasts";
                enableServe = mkEnableOption "serve-podcasts";
                podcastDir = mkOption {
                  type = types.str;
                  default = stateDirectory + "podcasts";
                };
                startAt = mkOption {
                  type = types.str;
                  default = "daily";
                };
              };
            };
            config = lib.mkIf (cfg.enableFetch || cfg.enableServe) {
              systemd.services.fetch-podcasts = {
                enable = cfg.enableFetch;
                script = "${fetch-podcasts} ${cfg.podcastDir} ${stateDirectory}";
                serviceConfig = commonServiceConfig // {
                  Type = "oneshot";
                  BindPaths = [ cfg.podcastDir ];
                };
                startAt = cfg.startAt;
              };
              systemd.services.serve-podcasts = {
                enable = cfg.enableServe;
                serviceConfig = commonServiceConfig // {
                  BindReadOnlyPaths = [ cfg.podcastDir ];
                  # TODO get port from cfg
                  ExecStart = ''
                    ${pkgs.python3Packages.gunicorn}/bin/gunicorn -b 0.0.0.0:5998 podcasts.serve:app
                  '';
                };
                environment =
                  {
                    # TODO unify with cli args
                    PODCASTS_ANNEX_DIR = cfg.podcastDir;
                    PODCASTS_DATA_DIR = stateDirectory;
                    PYTHONPATH = "${penv}/${penv.sitePackages}";
                  };
                wantedBy = [ "multi-user.target" ];
                after = [ "network.target" ] ++ lib.optional cfg.enableFetch "fetch-podcasts.timer";
              };
            };
          };
      };
    in with utils.lib; eachSystem defaultSystems out;

}
