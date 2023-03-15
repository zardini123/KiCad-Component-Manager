# @TODO: Only run when not ran as script (i.e. imported as module for KiCad)
if False:
    import pcbnew

    # @TODO: Install kiutils from pip

    board = pcbnew.GetBoard()
    board_path = pcbnew.GetFileName()
