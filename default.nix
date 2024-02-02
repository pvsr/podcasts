{pkgs ? import <nixpkgs> {}}: let
  python = pkgs.python3;
in
  with python.pkgs;
    buildPythonPackage rec {
      pname = "podcasts";
      version = "0.1.0";
      src = ./.;
      format = "pyproject";
      nativeBuildInputs = [setuptools];
      propagatedBuildInputs = [requests feedparser pyyaml dacite sqlalchemy flask flask-httpauth flask-sqlalchemy];
      passthru = {
        inherit python;
      };
    }
