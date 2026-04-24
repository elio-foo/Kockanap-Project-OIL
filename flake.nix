{
	description = "Project dev shell";

	inputs = {
		nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
	};

	outputs = { self, nixpkgs }:
	let
		system = "x86_64-linux";
		pkgs = import nixpkgs { inherit system; };
	in {
		devShells.${system}.default = pkgs.mkShell {
			packages = [
				(pkgs.python313.withPackages (python-pkgs: with python-pkgs; [
					grpcio
				]))
			];
		};
	};
}
