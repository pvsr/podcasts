{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    utils,
  }: let
    out = system: let
      pkgs = nixpkgs.legacyPackages."${system}";
      devEnv = pkgs.poetry2nix.mkPoetryEnv {
        projectDir = ./.;
        preferWheels = true;
      };
    in rec {
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
        drv = packages.default;
        exePath = "/bin/fetch-podcasts";
      };

      formatter = pkgs.alejandra;
    };
  in
    with utils.lib;
      eachSystem defaultSystems out
      // {
        nixosModules.default = {
          config,
          lib,
          pkgs,
          ...
        }: let
          cfg = config.services.podcasts;
          podcasts = self.outputs.packages."${pkgs.system}".default;
          penv = podcasts.dependencyEnv;
          stateDirectory = "/var/lib/podcasts/";
          podcastDir = "${cfg.annexDir}/${cfg.podcastSubdir}";
          commonServiceConfig = {
            StateDirectory = "podcasts";
            # TODO more hardening
            PrivateTmp = true;
            RemoveIPC = true;
            NoNewPrivileges = true;
            ProtectSystem = "strict";
            ProtectHome = "read-only";
            RestrictSUIDSGID = true;
          };
        in {
          options = {
            services.podcasts = with lib; {
              annexDir = mkOption {
                type = types.str;
                default = stateDirectory + "annex";
              };
              podcastSubdir = mkOption {
                type = types.str;
                default = "hosted-podcasts";
              };
              dataDir = mkOption {
                type = types.str;
                default = stateDirectory;
              };
              fetch = {
                enable = mkEnableOption "fetch-podcasts";
                user = mkOption {
                  type = types.str;
                  default = "podcasts";
                };
                group = mkOption {
                  type = types.str;
                  default = "podcasts";
                };
                startAt = mkOption {
                  type = with types; either str (listOf str);
                  default = "daily";
                };
              };
              serve = {
                enable = mkEnableOption "serve-podcasts";
                user = mkOption {
                  type = types.str;
                  default = "podcasts";
                };
                group = mkOption {
                  type = types.str;
                  default = "podcasts";
                };
                bind = mkOption {
                  type = types.str;
                  default = "127.0.0.1:5998";
                };
              };
            };
          };
          config = lib.mkIf (cfg.fetch.enable || cfg.serve.enable) {
            systemd.services.fetch-podcasts = {
              inherit (cfg.fetch) enable startAt;
              path = [pkgs.git pkgs.git-annex];
              serviceConfig =
                commonServiceConfig
                // {
                  User = cfg.fetch.user;
                  Group = cfg.fetch.group;
                  Type = "oneshot";
                  BindPaths = [cfg.annexDir cfg.dataDir];
                  ExecStart = "${podcasts}/bin/fetch-podcasts";
                };
              environment = {
                PODCASTS_ANNEX_DIR = podcastDir;
                PODCASTS_DATA_DIR = cfg.dataDir;
              };
            };
            systemd.services.serve-podcasts = {
              inherit (cfg.serve) enable;
              serviceConfig =
                commonServiceConfig
                // {
                  User = cfg.serve.user;
                  Group = cfg.serve.group;
                  BindReadOnlyPaths = [podcastDir cfg.dataDir];
                  ExecStart = ''
                    ${pkgs.python3Packages.gunicorn}/bin/gunicorn -b ${cfg.serve.bind} podcasts.serve:app
                  '';
                };
              environment = {
                PODCASTS_ANNEX_DIR = podcastDir;
                PODCASTS_DATA_DIR = cfg.dataDir;
                PODCASTS_DOMAIN = "https://podcasts.peterrice.xyz";
                PYTHONPATH = "${penv}/${penv.sitePackages}";
              };
              wantedBy = ["multi-user.target"];
              after = ["network.target"] ++ lib.optional cfg.fetch.enable "fetch-podcasts.timer";
            };

            users.users = lib.mkIf (cfg.fetch.user == "podcasts" || cfg.serve.user == "podcasts") {
              podcasts = {
                isSystemUser = true;
                group = "podcasts";
                home = stateDirectory;
              };
            };

            users.groups = lib.mkIf (cfg.fetch.group == "podcasts" || cfg.serve.group == "podcasts") {
              podcasts = {};
            };
          };
        };
      };
}
