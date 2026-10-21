"""Per-pair persistent arrays and constants from Pine 4.1.22."""
from . import runtime as rt

def update(e):
    # Pine 631
    if 'fvgBullLow' not in e.persistent:
        e.initialize('fvgBullLow', rt.arr_new_float())
    # Pine 632
    if 'fvgBullHigh' not in e.persistent:
        e.initialize('fvgBullHigh', rt.arr_new_float())
    # Pine 633
    if 'fvgBearLow' not in e.persistent:
        e.initialize('fvgBearLow', rt.arr_new_float())
    # Pine 634
    if 'fvgBearHigh' not in e.persistent:
        e.initialize('fvgBearHigh', rt.arr_new_float())
    # Pine 635
    if 'fvgBullStrength' not in e.persistent:
        e.initialize('fvgBullStrength', rt.arr_new_float())
    # Pine 636
    if 'fvgBearStrength' not in e.persistent:
        e.initialize('fvgBearStrength', rt.arr_new_float())
    # Pine 637
    if 'fvgBullReaction' not in e.persistent:
        e.initialize('fvgBullReaction', rt.arr_new_float())
    # Pine 638
    if 'fvgBearReaction' not in e.persistent:
        e.initialize('fvgBearReaction', rt.arr_new_float())
    # Pine 639
    if 'fvgBullStatus' not in e.persistent:
        e.initialize('fvgBullStatus', rt.arr_new_int())
    # Pine 640
    if 'fvgBearStatus' not in e.persistent:
        e.initialize('fvgBearStatus', rt.arr_new_int())
    # Pine 641
    if 'fvgBullAge' not in e.persistent:
        e.initialize('fvgBullAge', rt.arr_new_int())
    # Pine 642
    if 'fvgBearAge' not in e.persistent:
        e.initialize('fvgBearAge', rt.arr_new_int())
    # Pine 643
    if 'fvgBullCreatedBar' not in e.persistent:
        e.initialize('fvgBullCreatedBar', rt.arr_new_int())
    # Pine 644
    if 'fvgBearCreatedBar' not in e.persistent:
        e.initialize('fvgBearCreatedBar', rt.arr_new_int())
    # Pine 645
    if 'fvgBullReactionCount' not in e.persistent:
        e.initialize('fvgBullReactionCount', rt.arr_new_int())
    # Pine 646
    if 'fvgBearReactionCount' not in e.persistent:
        e.initialize('fvgBearReactionCount', rt.arr_new_int())
    # Pine 647
    if 'fvgBullLastReactionBar' not in e.persistent:
        e.initialize('fvgBullLastReactionBar', rt.arr_new_int())
    # Pine 648
    if 'fvgBearLastReactionBar' not in e.persistent:
        e.initialize('fvgBearLastReactionBar', rt.arr_new_int())
    # Pine 649
    if 'fvgBullReactionActive' not in e.persistent:
        e.initialize('fvgBullReactionActive', rt.arr_new_bool())
    # Pine 650
    if 'fvgBearReactionActive' not in e.persistent:
        e.initialize('fvgBearReactionActive', rt.arr_new_bool())
    # Pine 651
    if 'fvgBullLastReactionType' not in e.persistent:
        e.initialize('fvgBullLastReactionType', rt.arr_new_int())
    # Pine 652
    if 'fvgBearLastReactionType' not in e.persistent:
        e.initialize('fvgBearLastReactionType', rt.arr_new_int())
    # Pine 653
    if 'fvgBullReactionScore' not in e.persistent:
        e.initialize('fvgBullReactionScore', rt.arr_new_int())
    # Pine 654
    if 'fvgBearReactionScore' not in e.persistent:
        e.initialize('fvgBearReactionScore', rt.arr_new_int())
    # Pine 657
    if 'FVG_STATUS_NONE' not in e.persistent:
        e.initialize('FVG_STATUS_NONE', 0)
    # Pine 658
    if 'FVG_STATUS_FRESH' not in e.persistent:
        e.initialize('FVG_STATUS_FRESH', 1)
    # Pine 659
    if 'FVG_STATUS_TESTED' not in e.persistent:
        e.initialize('FVG_STATUS_TESTED', 2)
    # Pine 660
    if 'FVG_STATUS_DEFENDED' not in e.persistent:
        e.initialize('FVG_STATUS_DEFENDED', 3)
    # Pine 661
    if 'FVG_REACTION_NONE' not in e.persistent:
        e.initialize('FVG_REACTION_NONE', 0)
    # Pine 662
    if 'FVG_WEAK_TOUCH' not in e.persistent:
        e.initialize('FVG_WEAK_TOUCH', 1)
    # Pine 663
    if 'FVG_STRONG_TOUCH' not in e.persistent:
        e.initialize('FVG_STRONG_TOUCH', 2)
    # Pine 664
    if 'FVG_INVALIDATED' not in e.persistent:
        e.initialize('FVG_INVALIDATED', 3)
    # Pine 665
    if 'FVG_FAILURE_MEMORY_BARS' not in e.persistent:
        e.initialize('FVG_FAILURE_MEMORY_BARS', 50)
    # Pine 679
    if 'supportZoneIDArray' not in e.persistent:
        e.initialize('supportZoneIDArray', rt.arr_new_string())
    # Pine 680
    if 'resistanceZoneIDArray' not in e.persistent:
        e.initialize('resistanceZoneIDArray', rt.arr_new_string())
    # Pine 683
    if 'supportLowArray' not in e.persistent:
        e.initialize('supportLowArray', rt.arr_new_float())
    # Pine 684
    if 'supportHighArray' not in e.persistent:
        e.initialize('supportHighArray', rt.arr_new_float())
    # Pine 685
    if 'supportOriginArray' not in e.persistent:
        e.initialize('supportOriginArray', rt.arr_new_float())
    # Pine 686
    if 'supportBarArray' not in e.persistent:
        e.initialize('supportBarArray', rt.arr_new_int())
    # Pine 687
    if 'supportTouchArray' not in e.persistent:
        e.initialize('supportTouchArray', rt.arr_new_int())
    # Pine 688
    if 'supportZoneATRArray' not in e.persistent:
        e.initialize('supportZoneATRArray', rt.arr_new_float())
    # Pine 689
    if 'prevCandleInsideSupportZoneArray' not in e.persistent:
        e.initialize('prevCandleInsideSupportZoneArray', rt.arr_new_bool())
    # Pine 690
    if 'supportLastTestBarArray' not in e.persistent:
        e.initialize('supportLastTestBarArray', rt.arr_new_int())
    # Pine 691
    if 'supportLastTestTypeArray' not in e.persistent:
        e.initialize('supportLastTestTypeArray', rt.arr_new_string())
    # Pine 692
    if 'supportStrengthArray' not in e.persistent:
        e.initialize('supportStrengthArray', rt.arr_new_float())
    # Pine 693
    if 'supportStrongRejectArray' not in e.persistent:
        e.initialize('supportStrongRejectArray', rt.arr_new_int())
    # Pine 694
    if 'supportMaxPenetrationArray' not in e.persistent:
        e.initialize('supportMaxPenetrationArray', rt.arr_new_float())
    # Pine 695
    if 'supportMaxWickRatioArray' not in e.persistent:
        e.initialize('supportMaxWickRatioArray', rt.arr_new_float())
    # Pine 696
    if 'supportMaxReactionArray' not in e.persistent:
        e.initialize('supportMaxReactionArray', rt.arr_new_float())
    # Pine 697
    if 'supportApproachDirectionArray' not in e.persistent:
        e.initialize('supportApproachDirectionArray', rt.arr_new_int())
    # Pine 698
    if 'supportOriginTimeArray' not in e.persistent:
        e.initialize('supportOriginTimeArray', rt.arr_new_int())
    # Pine 699
    if 'supportScoreArray' not in e.persistent:
        e.initialize('supportScoreArray', rt.arr_new_float())
    # Pine 700
    if 'supportESArray' not in e.persistent:
        e.initialize('supportESArray', rt.arr_new_float())
    # Pine 703
    if 'resistanceLowArray' not in e.persistent:
        e.initialize('resistanceLowArray', rt.arr_new_float())
    # Pine 704
    if 'resistanceHighArray' not in e.persistent:
        e.initialize('resistanceHighArray', rt.arr_new_float())
    # Pine 705
    if 'resistanceOriginArray' not in e.persistent:
        e.initialize('resistanceOriginArray', rt.arr_new_float())
    # Pine 706
    if 'resistanceBarArray' not in e.persistent:
        e.initialize('resistanceBarArray', rt.arr_new_int())
    # Pine 707
    if 'resistanceTouchArray' not in e.persistent:
        e.initialize('resistanceTouchArray', rt.arr_new_int())
    # Pine 708
    if 'prevCandleInsideResistanceZoneArray' not in e.persistent:
        e.initialize('prevCandleInsideResistanceZoneArray', rt.arr_new_bool())
    # Pine 709
    if 'resistanceLastTestBarArray' not in e.persistent:
        e.initialize('resistanceLastTestBarArray', rt.arr_new_int())
    # Pine 710
    if 'resistanceLastTestTypeArray' not in e.persistent:
        e.initialize('resistanceLastTestTypeArray', rt.arr_new_string())
    # Pine 711
    if 'resistanceStrengthArray' not in e.persistent:
        e.initialize('resistanceStrengthArray', rt.arr_new_float())
    # Pine 712
    if 'resistanceStrongRejectArray' not in e.persistent:
        e.initialize('resistanceStrongRejectArray', rt.arr_new_int())
    # Pine 713
    if 'resistanceMaxPenetrationArray' not in e.persistent:
        e.initialize('resistanceMaxPenetrationArray', rt.arr_new_float())
    # Pine 714
    if 'resistanceMaxWickRatioArray' not in e.persistent:
        e.initialize('resistanceMaxWickRatioArray', rt.arr_new_float())
    # Pine 715
    if 'resistanceMaxReactionArray' not in e.persistent:
        e.initialize('resistanceMaxReactionArray', rt.arr_new_float())
    # Pine 716
    if 'resistanceApproachDirectionArray' not in e.persistent:
        e.initialize('resistanceApproachDirectionArray', rt.arr_new_int())
    # Pine 717
    if 'resistanceOriginTimeArray' not in e.persistent:
        e.initialize('resistanceOriginTimeArray', rt.arr_new_int())
    # Pine 718
    if 'resistanceScoreArray' not in e.persistent:
        e.initialize('resistanceScoreArray', rt.arr_new_float())
    # Pine 719
    if 'resistanceESArray' not in e.persistent:
        e.initialize('resistanceESArray', rt.arr_new_float())
    # Pine 720
    if 'resistanceZoneATRArray' not in e.persistent:
        e.initialize('resistanceZoneATRArray', rt.arr_new_float())
    # Pine 733
    if 'instSupportZoneIDArray' not in e.persistent:
        e.initialize('instSupportZoneIDArray', rt.arr_new_string())
    # Pine 734
    if 'instSupportScoreArray' not in e.persistent:
        e.initialize('instSupportScoreArray', rt.arr_new_float())
    # Pine 735
    if 'instSupportStrengthArray' not in e.persistent:
        e.initialize('instSupportStrengthArray', rt.arr_new_int())
    # Pine 736
    if 'instQualifiedSupportTFListArray' not in e.persistent:
        e.initialize('instQualifiedSupportTFListArray', rt.arr_new_string())
    # Pine 737
    if 'instSupportFailureCountArray' not in e.persistent:
        e.initialize('instSupportFailureCountArray', rt.arr_new_int())
    # Pine 738
    if 'InstSupportBreakBarArray' not in e.persistent:
        e.initialize('InstSupportBreakBarArray', rt.arr_new_int())
    # Pine 741
    if 'instResistanceZoneIDArray' not in e.persistent:
        e.initialize('instResistanceZoneIDArray', rt.arr_new_string())
    # Pine 742
    if 'instResistanceScoreArray' not in e.persistent:
        e.initialize('instResistanceScoreArray', rt.arr_new_float())
    # Pine 743
    if 'instResistanceStrengthArray' not in e.persistent:
        e.initialize('instResistanceStrengthArray', rt.arr_new_int())
    # Pine 744
    if 'instQualifiedResistanceTFListArray' not in e.persistent:
        e.initialize('instQualifiedResistanceTFListArray', rt.arr_new_string())
    # Pine 745
    if 'instResistanceFailureCountArray' not in e.persistent:
        e.initialize('instResistanceFailureCountArray', rt.arr_new_int())
    # Pine 746
    if 'InstResistanceBreakBarArray' not in e.persistent:
        e.initialize('InstResistanceBreakBarArray', rt.arr_new_int())
    # Pine 749
    if 'swingHighPriceArray' not in e.persistent:
        e.initialize('swingHighPriceArray', rt.arr_new_float())
    # Pine 750
    if 'swingHighBarArray' not in e.persistent:
        e.initialize('swingHighBarArray', rt.arr_new_int())
    # Pine 751
    if 'swingHighTimeArray' not in e.persistent:
        e.initialize('swingHighTimeArray', rt.arr_new_int())
    # Pine 752
    if 'swingLowPriceArray' not in e.persistent:
        e.initialize('swingLowPriceArray', rt.arr_new_float())
    # Pine 753
    if 'swingLowBarArray' not in e.persistent:
        e.initialize('swingLowBarArray', rt.arr_new_int())
    # Pine 754
    if 'swingLowTimeArray' not in e.persistent:
        e.initialize('swingLowTimeArray', rt.arr_new_int())
    # Pine 755
    if 'currentActivePivotTypeArray' not in e.persistent:
        e.initialize('currentActivePivotTypeArray', rt.arr_new_int())
    # Pine 756
    if 'prevActivePivotTypeArray' not in e.persistent:
        e.initialize('prevActivePivotTypeArray', rt.arr_new_int())
    # Pine 759
    if 'structurePivotHigh' not in e.persistent:
        e.initialize('structurePivotHigh', rt.arr_new_float())
    # Pine 760
    if 'structurePivotHighBar' not in e.persistent:
        e.initialize('structurePivotHighBar', rt.arr_new_int())
    # Pine 761
    if 'structurePivotLow' not in e.persistent:
        e.initialize('structurePivotLow', rt.arr_new_float())
    # Pine 762
    if 'structurePivotLowBar' not in e.persistent:
        e.initialize('structurePivotLowBar', rt.arr_new_int())
    # Pine 763
    if 'structureHighType' not in e.persistent:
        e.initialize('structureHighType', rt.arr_new_string())
    # Pine 764
    if 'structureLowType' not in e.persistent:
        e.initialize('structureLowType', rt.arr_new_string())
    # Pine 765
    if 'structureState' not in e.persistent:
        e.initialize('structureState', rt.arr_new_string())
    # Pine 766
    if 'structureHighsCount' not in e.persistent:
        e.initialize('structureHighsCount', rt.arr_new_int())
    # Pine 767
    if 'structureLowsCount' not in e.persistent:
        e.initialize('structureLowsCount', rt.arr_new_int())
    # Pine 768
    if 'structureTransition' not in e.persistent:
        e.initialize('structureTransition', rt.arr_new_string())
    # Pine 769
    if 'structureBOS' not in e.persistent:
        e.initialize('structureBOS', rt.arr_new_string())
    # Pine 770
    if 'structureCHOCH' not in e.persistent:
        e.initialize('structureCHOCH', rt.arr_new_string())
    # Pine 773
    if 'executionTF' not in e.persistent:
        e.initialize('executionTF', rt.arr_new_string())
    # Pine 774
    if 'executionBar' not in e.persistent:
        e.initialize('executionBar', rt.arr_new_int())
    # Pine 775
    if 'executionTime' not in e.persistent:
        e.initialize('executionTime', rt.arr_new_int())
    # Pine 776
    if 'executionType' not in e.persistent:
        e.initialize('executionType', rt.arr_new_string())
    # Pine 777
    if 'executionTypeCount' not in e.persistent:
        e.initialize('executionTypeCount', rt.arr_new_int())
    # Pine 778
    if 'prevExecutionType' not in e.persistent:
        e.initialize('prevExecutionType', rt.arr_new_string())
    # Pine 779
    if 'prevExecutionBar' not in e.persistent:
        e.initialize('prevExecutionBar', rt.arr_new_int())
