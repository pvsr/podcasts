{ pkgs ? import <nixpkgs> { }, ... }:
with pkgs;
mkShell {
  buildInputs = [
    (python3.withPackages (ps: with ps; [
      pylint
      mypy
      black

      requests
      feedparser
      num2words
      pyyaml
    ]))
  ];
}
