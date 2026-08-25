from sefa import cli


def test_default_output_path_is_top_output():
    print(cli.default_output_folder_abs_path)
    assert cli.default_output_folder_abs_path.endswith("/output")
    assert not cli.default_output_folder_abs_path.endswith("/src/sefa/output")
