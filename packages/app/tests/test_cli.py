from argus_app.cli import main


def test_no_subcommand_exits_2():
    assert main([]) == 2
