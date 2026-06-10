import logging
import os

import polars as pl
from Bio import SeqIO
from Bio.SeqFeature import FeatureLocation, SeqFeature


class IROperations:

    def __init__(self, fp_record):
        self.log = logging.getLogger(__name__)
        if not os.path.isfile(fp_record):
            raise FileNotFoundError(f"Unable to find '{fp_record}'")
        try:
            self.rec = SeqIO.read(fp_record, "genbank")
            try:
                self.IRa, self.IRb = self.identify_inverted_repeats(self.rec)
            except Exception:
                self.IRa, self.IRb = None, None
            self.info = self.collect_info_from_features(self.IRa, self.IRb)
        except Exception as err:
            raise Exception(f"Error processing record '{fp_record}': {err}")

    ###############
    # I/O methods #
    ###############

    def read_record(self, fp_record):
        '''
        Reads a GenBank flat file and returns it as SeqRecord
        '''
        rec = None
        if os.path.isfile(fp_record):
            accession = os.path.splitext(fp_record)[0]
            try:
                rec = SeqIO.read(fp_record, "genbank")
            except Exception as err:
                raise Exception(
                    "Error reading record of accession `%s`: %s. Skipping this accession." %
                    (str(accession), str(err)))
        else:
            raise Exception(
                "Error reading record: Unable to find '%s'." %
                (fp_record))
        return rec

    ##################################
    # feature identification methods #
    ##################################

    def identify_junction(self, feature, rec_len):
        '''
        Evaluates if a feature is a junction between an inverted repeat and a single copy region,
        and returns the appropriate junction type as an integer.
        The function checks for hard identifiers first, then tries to infer
        the type through soft identifiers
        Params:
         - feature: the SeqFeature
         - rec_len: length of the SeqRecord
        Return values:
        -1: Feature cannot be identified as junction
        0:  Feature is identified as JLB (junction LSC -> IRb)
        1:  Feature is identified as JSB (junction IRb -> SSC)
        2:  Feature is identified as JSA (junction SSC -> IRa)
        3:  Feature is  identified as JLA (junction IRa -> LSC)
        4:  Ambiguous (more than one possible junction type found)
        '''
        junction_type = None

        if len(feature) < 3:
            identified = False
            possible_junctions = []
            junction_note = feature.qualifiers.get("note", [""])[0].lower()

            jlb_identifiers = {
                "hard": [
                    "jlb",
                    "lsc-irb",
                    "irb-lsc"],
                "soft": [
                    "lsc-ir",
                    "ir-lsc"]}
            jsb_identifiers = {
                "hard": [
                    "jsb",
                    "ssc-irb",
                    "irb-ssc"],
                "soft": [
                    "ssc-ir",
                    "ir-ssc"]}
            jsa_identifiers = {
                "hard": [
                    "jsa",
                    "ssc-ira",
                    "ira-ssc"],
                "soft": [
                    "ssc-ir",
                    "ir-ssc"]}
            jla_identifiers = {
                "hard": [
                    "jla",
                    "ira-lsc",
                    "lsc-ira"],
                "soft": [
                    "lsc-ir",
                    "ir-lsc"]}

            if any(
                    identifier in junction_note for identifier in jlb_identifiers["hard"]):
                junction_type = 0
                identified = True
            elif any(identifier in junction_note for identifier in jlb_identifiers["soft"]):
                possible_junctions.append(0)

            if not identified:
                if any(
                        identifier in junction_note for identifier in jsb_identifiers["hard"]):
                    junction_type = 1
                    identified = True
                elif any(identifier in junction_note for identifier in jsb_identifiers["soft"]):
                    possible_junctions.append(1)

            if not identified:
                if any(
                        identifier in junction_note for identifier in jsa_identifiers["hard"]):
                    junction_type = 2
                    identified = True
                elif any(identifier in junction_note for identifier in jsa_identifiers["soft"]):
                    possible_junctions.append(2)

            if not identified:
                if any(
                        identifier in junction_note for identifier in jla_identifiers["hard"]):
                    junction_type = 3
                    identified = True
                elif any(identifier in junction_note for identifier in jla_identifiers["soft"]):
                    possible_junctions.append(3)

            if not identified:
                if len(possible_junctions) == 1:
                    junction_type = possible_junctions[0]
                elif len(possible_junctions) > 1:
                    junction_type = 4
                    # if the feature is located at the end of the sequence,
                    # it is most certainly a JLA
                    # NOTE: There are exceptions to this rule.
                    if 3 in possible_junctions:
                        if feature.location.start in range(
                                rec_len - 10, rec_len):
                            identified = True
                            junction_type = 3
                        else:
                            # if there is only one other junction type in
                            # consideration, pick it
                            if len(possible_junctions) == 2:
                                identified = True
                                junction_type = possible_junctions[0]
                else:
                    junction_type = -1
        else:
            junction_type = -1
        return junction_type

    def infer_irs_from_junctions(self, rec_len, all_misc_features):
        '''
        Tries to infer the IR positions from the information provided by the junction features;
        returns the IRs as full features.
        Params:
         - rec_len: length of the SeqRecord
         - all_misc_features: list of "misc_feature" SeqFeatures
        '''
        IRa = None
        IRb = None
        jlb_feat = None
        jsb_feat = None
        jsa_feat = None
        jla_feat = None

        i = 0
        for misc_feature in [
                mf for mf in all_misc_features if "note" in mf.qualifiers]:
            i += 1
            self.log.debug(
                "Checking misc_feature %s out of %s (position %s - %s)..." %
                (str(i), str(
                    len(all_misc_features)), str(
                    misc_feature.location.start), str(
                    misc_feature.location.end)))
            junction_type = self.identify_junction(misc_feature, rec_len)
            if junction_type == 0:  # JLB
                self.log.debug("Found junction LSC-IRb.")
                jlb_feat = misc_feature
            elif junction_type == 1:  # JSB
                self.log.debug("Found junction IRb-SSC.")
                jsb_feat = misc_feature
            elif junction_type == 2:  # JSA
                self.log.debug("Found junction SSC-IRa.")
                jsa_feat = misc_feature
            elif junction_type == 3:  # JLA
                self.log.debug("Found junction IRa-LSC")
                jla_feat = misc_feature
            elif junction_type == 4:  # Ambiguous
                self.log.debug(
                    "Found a junction but its identifiers are ambiguous.")

        for junction in [jlb_feat, jsb_feat, jsa_feat, jla_feat]:
            junction = self.adjust_feature_location(junction)
        if jlb_feat and jsb_feat:
            self.log.debug("Constructing IRb from found junctions.")
            if jlb_feat.location.start < jsb_feat.location.start:
                IRb = SeqFeature(
                    FeatureLocation(
                        jlb_feat.location.end - 1,
                        jsb_feat.location.start + 1,
                        strand=1))
            else:
                IRb = SeqFeature(
                    FeatureLocation(
                        jsb_feat.location.end - 1,
                        jlb_feat.location.start + 1,
                        strand=1))
        if jsa_feat:
            self.log.debug("Constructing IRa from found junctions.")
            if jla_feat:
                # comparing start locations to see in which order the IRs and
                # SC regions are in the genome
                if jsa_feat.location.start < jla_feat.location.start:
                    IRa = SeqFeature(
                        FeatureLocation(
                            jsa_feat.location.end - 1,
                            jla_feat.location.start + 1,
                            strand=1))
                else:
                    IRa = SeqFeature(
                        FeatureLocation(
                            jla_feat.location.end - 1,
                            jsa_feat.location.start + 1,
                            strand=1))
            elif jsb_feat:
                # If JLA is not given, we assume that the plastid genome is split at the JLA
                # (i.e. start of the JLA is the last position in the sequence,
                # end of the JLA is the first position)
                if jsb_feat.location.start < jsa_feat.location.start:
                    IRa = SeqFeature(
                        FeatureLocation(
                            jsa_feat.location.end - 1,
                            rec_len,
                            strand=1))
                else:
                    IRa = SeqFeature(
                        FeatureLocation(
                            0,
                            jsa_feat.location.start + 1,
                            strand=1))
            else:
                # if JSB is not given either, we assume the plastid genome follows the
                # convention of (start:LSC|IRb|SSC|IRa:end)
                IRa = SeqFeature(
                    FeatureLocation(
                        jsa_feat.location.end - 1,
                        rec_len,
                        strand=1))
        return IRa, IRb

    def infer_irs_from_single_copy_regions(
            self, rec_len, all_mf_no_pseudo, IRa=None, IRb=None):
        '''
        Tries to infer the IR positions from the information provided by the single copy features;
        returns the IRs as full features
        Params:
         - rec_len: length of the record
         - all_mf_no_pseudo: list of "misc_feature" SeqFeatures excluding pseudo features
         - IRa: SeqFeature that corresponds to Inverted Repeat A
         - IRb: SeqFeature that corresponds to Inverted Repeat B
        '''
        ssc = None
        lsc = None
        ssc_identifiers = ["ssc", "small single copy"]
        lsc_identifiers = ["lsc", "large single copy"]
        blocklist = ["jlb", "jsb", "jsa", "jla", "junction"]
        i = 0
        for misc_feature in [
                mf for mf in all_mf_no_pseudo if "note" in mf.qualifiers]:
            i += 1
            note_text = misc_feature.qualifiers["note"][0].lower()
            self.log.debug(
                "Checking misc_feature %s out of %s (position %s - %s)..." %
                (str(i), str(
                    len(all_mf_no_pseudo)), str(
                    misc_feature.location.start), str(
                    misc_feature.location.end)))
            if any(identifier in note_text for identifier in ssc_identifiers) and not any(
                    blocked in note_text for blocked in blocklist):
                self.log.debug("Found identifier for SSC")
                ssc = misc_feature
            if any(identifier in note_text for identifier in lsc_identifiers) and not any(
                    blocked in note_text for blocked in blocklist):
                self.log.debug("Found identifier for LSC")
                lsc = misc_feature
        if lsc and ssc:
            if lsc.location.start < ssc.location.start:
                ira_start = ssc.location.end - 1
                ira_end = lsc.location.start
                irb_start = lsc.location.end - 1
                irb_end = ssc.location.start
                if ira_end == 0:
                    ira_end = rec_len
                if IRa is None:
                    self.log.debug(
                        "Constructing IRa from found single-copy positions.")
                    IRa = SeqFeature(
                        FeatureLocation(
                            ira_start,
                            ira_end),
                        type="misc_feature",
                        strand=1)
                if IRb is None:
                    self.log.debug(
                        "Constructing IRb from found single-copy positions.")
                    IRb = SeqFeature(
                        FeatureLocation(
                            irb_start,
                            irb_end),
                        type="misc_feature",
                        strand=1)
            else:
                ira_start = lsc.location.end - 1
                ira_end = ssc.location.start
                irb_start = ssc.location.end - 1
                irb_end = lsc.location.start
                if irb_end == 0:
                    irb_end = rec_len
                if IRa is None:
                    self.log.debug(
                        "Constructing IRa from found single-copy positions.")
                    IRa = SeqFeature(
                        FeatureLocation(
                            lsc.location.end - 1,
                            ssc.location.start),
                        type="misc_feature",
                        strand=1)
                if IRb is None:
                    self.log.debug(
                        "Constructing IRb from found single-copy positions.")
                    IRb = SeqFeature(
                        FeatureLocation(
                            ssc.location.end - 1,
                            lsc.location.start),
                        type="misc_feature",
                        strand=1)
        return IRa, IRb

    def identify_irs_in_misc_features(
            self, all_mf_no_pseudo, IRa=None, IRb=None):
        '''
        Tries to infer the IR positions from the information provided by the
        misc_features; returns the IRs as full features
        Params:
         - all_mf_no_pseudo: list of "misc_feature" SeqFeatures excluding pseudo features
         - IRa: SeqFeature that corresponds to Inverted Repeat A
         - IRb: SeqFeature that corresponds to Inverted Repeat B
        '''
        ira_identifiers = ["ira", "inverted repeat a"]
        irb_identifiers = ["irb", "inverted repeat b"]
        blocklist = ["jlb", "jsb", "jsa", "jla", "junction"]
        # STEP 1: Check for hard identifiers
        for misc_feature in [
                mf for mf in all_mf_no_pseudo if "note" in mf.qualifiers]:
            note_text = misc_feature.qualifiers["note"][0].lower()
            if IRa is None:
                if any(
                        identifier in note_text for identifier in ira_identifiers) and not any(
                        blocked in note_text for blocked in blocklist):
                    self.log.debug(
                        "Found identifier for IRa: `%s`" % str(
                            misc_feature.qualifiers["note"][0]))
                    if len(misc_feature) > 100:
                        IRa = misc_feature
                    else:
                        self.log.debug(
                            "Feature is too short (%s bp) to be an IR." % str(
                                len(misc_feature)))
            if IRb is None:
                if any(
                        identifier in note_text for identifier in irb_identifiers) and not any(
                        blocked in note_text for blocked in blocklist):
                    self.log.debug(
                        "Found identifier for IRb: `%s`" % str(
                            misc_feature.qualifiers["note"][0]))
                    if len(misc_feature) > 100:
                        IRb = misc_feature
                    else:
                        self.log.debug(
                            "Feature is too short (%s bp) to be an IR." % str(
                                len(misc_feature)))
        # STEP 2: Check for soft identifiers
        if IRa is None or IRb is None:
            for misc_feature in [
                    mf for mf in all_mf_no_pseudo if "note" in mf.qualifiers]:
                note_text = misc_feature.qualifiers["note"][0].lower()
                if (("inverted" in note_text and
                     "repeat" in note_text) or "IR" in misc_feature.qualifiers["note"][0]) and \
                        not any(blocked in note_text for blocked in blocklist):
                    self.log.debug(
                        "Found general identifier for IRs: `%s`" % str(
                            misc_feature.qualifiers["note"][0]))
                    if len(misc_feature) > 100:
                        if IRb is None:
                            self.log.debug("Assign feature as IRb")
                            IRb = misc_feature
                        elif IRa is None:
                            self.log.debug("Assign feature as IRa")
                            IRa = misc_feature
                    else:
                        self.log.debug(
                            "Feature is too short (%s bp) to be an IR." % str(
                                len(misc_feature)))
        return IRa, IRb

    def identify_irs_in_repeat_features(
            self,
            all_repeat_features,
            IRa=None,
            IRb=None,
            min_IR_len=1000,
    ):
        '''
        Tries to infer the IR positions from the information provided by the
        repeat_features; returns the IRs as SeqFeatures
        Params:
         - all_repeat_features: list of "repeat_feature" SeqFeatures
         - IRa: SeqFeature that corresponds to Inverted Repeat A
         - IRb: SeqFeature that corresponds to Inverted Repeat B
         - min_IR_len: minimum length identified IRs must have.
        '''
        ira_identifiers = ["ira", "inverted repeat a"]
        irb_identifiers = ["irb", "inverted repeat b"]
        # Loop through repeat_regions and attempt to identify IRs
        self.log.debug(
            "Checking all repeat_features with 'rpt_type' qualifier for IR information...")
        i = 0
        for repeat_feature in [
                rf for rf in all_repeat_features if "rpt_type" in rf.qualifiers]:
            i += 1
            self.log.debug(
                "Checking repeat_feature %s out of %s (position %s - %s)..." %
                (str(i), str(
                    len(all_repeat_features)), str(
                    repeat_feature.location.start), str(
                    repeat_feature.location.end)))
            if repeat_feature.qualifiers["rpt_type"][0].lower() == "inverted":
                self.log.debug("Feature is of rpt_type=inverted")
                if len(repeat_feature) > min_IR_len:
                    if "note" in repeat_feature.qualifiers:
                        self.log.debug(
                            "Checking note qualifier for IR identifiers.")
                        # If the "note" qualifier contains explicit mention of which IR
                        # (a/b) we are looking at, assign it to the appropriate variable.
                        note_text = repeat_feature.qualifiers["note"][0].lower()
                        if any(identifier in note_text for identifier in ira_identifiers):
                            self.log.debug("Found identifier for IRa.")
                            IRa = repeat_feature
                        elif any(identifier in note_text for identifier in irb_identifiers):
                            self.log.debug("Found identifier for IRb.")
                            IRb = repeat_feature
                        # If the "note" qualifier holds no information on which IR
                        # we are looking at, assign the repeat feature to one of the
                        # variables that hasn't been initialized yet. IRb gets
                        # assigned first, since it is located before IRa in the
                        # sequence, so if there is no further information given, the
                        # first IR found
                        # is assumed to be IRb.
                        elif IRb is None:
                            self.log.debug(
                                "No specific identifier found. Assigned feature as IRb.")
                            IRb = repeat_feature
                        # Note: Elif-statement in this context assures that IRa
                        # is assigned only if IRb is not None.
                        elif IRa is None:
                            self.log.debug(
                                "No specific identifier found. Assigned feature as IRa.")
                            IRa = repeat_feature
                    # If the "note" qualifier does not exist, assign the repeat
                    # feature to one of the variables that hasn't been initialized
                    # yet. IRb gets assigned first, since it is located before IRa
                    # in the sequence, so if there is no further information
                    # given, the first IR found is assumed to be IRb.
                    elif IRb is None:
                        self.log.debug(
                            "No 'note' qualifier found. Assigned feature as IRb.")
                        IRb = repeat_feature
                    # Note: Elif-statement in this context assures that IRa is
                    # assigned only if IRb is not None.
                    elif IRa is None:
                        self.log.debug(
                            "No 'note' qualifier found. Assigned feature as IRa.")
                        IRa = repeat_feature
                else:
                    self.log.info(
                        "Inverted repeat feature detected at position %s - %s. Region is too small "
                        "(smaller than %s bp) to be IRa or IRb." %
                        (str(
                            repeat_feature.location.start), str(
                            repeat_feature.location.end), str(min_IR_len), ))
        if IRa is None or IRb is None:
            self.log.debug(
                "%s out of 2 IR positions found so far. Checking repeat_features "
                "without 'rpt_type' qualifier." % (
                    str([IRa is None, IRb is None].count(False)),
                )
            )
            i = 0
            for repeat_feature in [
                feature
                for feature in all_repeat_features
                if "rpt_type" not in feature.qualifiers
            ]:
                i += 1
                self.log.debug(
                    "Checking repeat_feature %s out of %s (position %s - %s)..." %
                    (str(i), str(
                        len(all_repeat_features)), str(
                        repeat_feature.location.start), str(
                        repeat_feature.location.end), ))
                if "note" in repeat_feature.qualifiers:
                    note_text = repeat_feature.qualifiers["note"][0].lower()
                    self.log.debug(
                        "Checking note qualifier for IR identifiers...")
                    if any(identifier in note_text for identifier in ira_identifiers):
                        self.log.debug("Found identifier for IRa.")
                        IRa = repeat_feature
                    elif any(identifier in note_text for identifier in irb_identifiers):
                        self.log.debug("Found identifier for IRb.")
                        IRb = repeat_feature
                    elif (
                        (
                            "inverted" in repeat_feature.qualifiers["note"][0].lower()
                            and "repeat" in repeat_feature.qualifiers["note"][0].lower()
                        )
                        or "IR" in repeat_feature.qualifiers["note"][0]
                    ):
                        self.log.debug("Found general identifier for IRs.")
                        # IRb gets assigned first, since it is located before IRa in the sequence,
                        # so if there is no further information given, the first IR found is
                        # assumed to be IRb.
                        if IRb is None:
                            self.log.debug("Assign feature as IRb.")
                            IRb = repeat_feature
                        elif IRa is None:
                            self.log.debug("Assigned feature as IRa.")
                            IRa = repeat_feature
                    else:
                        self.log.info(
                            "Found a repeat region (%s - %s) without further identifying "
                            "information. Ignoring this feature." %
                            (str(
                                repeat_feature.location.start), str(
                                repeat_feature.location.end), ))

        return IRa, IRb

    def identify_inverted_repeats(self, rec, min_IR_len=1000):
        '''
        Tries to identify Inverted Repeats in a SeqRecord.
        Params:
         - rec: the SeqRecord
         - min_IR_len: minimum length identified IRs must have.
        Returns:
         - IRa: SeqFeature object corresponding to the SeqRecord's Inverted Repeat A
         - IRb: SeqFeature object corresponding to the SeqRecord's Inverted Repeat B
        '''
        IRa = None
        IRb = None
        self.log.debug("Trying to determine IRs...")

        # STEP 1. Parse out all potentially relevant features
        all_repeat_features = [
            feature for feature in rec.features if feature.type == 'repeat_region']
        all_misc_features = [
            feature for feature in rec.features if feature.type == 'misc_feature']
        # Note: The following line prevents that pseudogenes (or related pseudo-features)
        #       are used to infer the IR length.
        all_mf_no_pseudo = [
            feature for feature in all_misc_features if 'pseudo' not in feature.qualifiers]

        if len(all_repeat_features) == 0 and len(all_misc_features) == 0:
            raise Exception(
                "Record does not contain any features which the IR are typically "
                "marked with (i.e., feature `repeat_region`, `misc_feature`).")

        # STEP 2: Loop through repeat_regions and attempt to identify IRs
        IRa, IRb = self.identify_irs_in_repeat_features(
            all_repeat_features, IRa, IRb, min_IR_len)

        # If no valid IRs found, check if the misc_features contain "note"
        # qualifiers necessary for identification
        if IRa is None and IRb is None:
            all_qualifiers = [
                misc_feature.qualifiers for misc_feature in all_misc_features]
            # The following line generates a nested list of all keys of all
            # qualifiers found in all misc features
            keylist = [list(q) for q in all_qualifiers]
            if "note" not in [key for keys in keylist for key in keys]:
                # Flatten the key list
                raise Exception(
                    "Record does not contain any qualifiers for feature `misc_feature` which "
                    "the IRs are typically named with (i.e., qualifier `note`).")

        # STEP 3. Loop through misc_features and attempt to identify IRs
        if IRa is None or IRb is None:
            self.log.debug(
                "%s out of 2 IR positions found so far. Checking all misc_features for "
                "identifying information in their NOTE QUALIFIERS..." % (
                    str([IRa is None, IRb is None].count(False)),
                )
            )
            IRa, IRb = self.identify_irs_in_misc_features(
                all_mf_no_pseudo, IRa, IRb)

        # Sanity check for IRs selected by the script so far
        if IRa is not None and len(IRa.extract(rec).seq) < min_IR_len:
            self.log.warning(
                "Selected IRa is too short to be a genuine IR and has been discarded.")
            IRa = None
        if IRb is not None and len(IRb.extract(rec).seq) < min_IR_len:
            self.log.warning(
                "Selected IRb is too short to be a genuine IR and has been discarded.")
            IRb = None

        # STEP 4. Loop through misc_features and attempt to identify junctions
        # from which to infer the IRs
        if IRa is None or IRb is None:
            self.log.debug(
                "%s out of 2 IR positions found so far. Checking all misc_features for "
                "JUNCTION INFORMATION..." % (
                    str([IRa is None, IRb is None].count(False)),
                )
            )
            IRa, IRb = self.infer_irs_from_junctions(
                len(rec), all_misc_features)

        # Sanity check for IRs selected by the script so far
        if IRa is not None and len(IRa.extract(rec).seq) < min_IR_len:
            self.log.warning(
                "Selected IRa is too short to be a genuine IR and has been discarded.")
            IRa = None
        if IRb is not None and len(IRb.extract(rec).seq) < min_IR_len:
            self.log.warning(
                "Selected IRb is too short to be a genuine IR and has been discarded.")
            IRb = None

        # STEP 5. Inferring the position of the IR implicitly by extracting the
        # positions of the large (LSC) and small single copy (SSC) regions and
        # calculating the IRs as the complement set thereof.
        if IRa is None or IRb is None:
            count_false = [IRa is None, IRb is None].count(False)
            self.log.debug(
                "%s out of 2 IR positions found so far. Trying to infer the missing IRs "
                "by given single-copy region positions..." %
                (str(count_false),)
            )
            if len(all_mf_no_pseudo) == 0:
                if IRa is None and IRb is None:
                    raise Exception(
                        "Record does not contain any features which the single-copy "
                        "regions are typically marked with (i.e., feature `misc_feature`).")
            IRa, IRb = self.infer_irs_from_single_copy_regions(
                len(rec), all_mf_no_pseudo, IRa, IRb)

        # Sanity check for IRs selected by the script so far
        if IRa is not None and len(IRa.extract(rec).seq) < min_IR_len:
            self.log.warning(
                "Selected IRa is too short to be a genuine IR and has been discarded.")
            IRa = None
        if IRb is not None and len(IRb.extract(rec).seq) < min_IR_len:
            self.log.warning(
                "Selected IRb is too short to be a genuine IR and has been discarded.")
            IRb = None

        if IRa is None and IRb is None:
            raise Exception(
                    "Record does not contain the information necessary to infer "
                    "the position of either the IR or the single-copy regions.")
        return IRa, IRb

    ########
    ########
    # MISC #
    ########

    def adjust_feature_location(self, feature):
        '''
        Checks that start and end position of a feature are not identical; if they are,
        make start position one bp less than end position; returns the adjusted feature
        (Some junctions in Genbank format are given as "start^end", leading to start and
        end positions being the same.)
        Params:
         - feature: the SeqFeature
        '''
        if feature:
            if feature.location.start == feature.location.end:
                # feature.location = FeatureLocation(feature.location.start-1,
                # feature.location.end, strand = feature.strand)  # Due to
                # warning: BiopythonDeprecationWarning: Please use
                # .location.strand rather than .strand
                feature.location = FeatureLocation(
                    feature.location.start - 1,
                    feature.location.end,
                    strand=feature.location.strand)
                self.log.debug(
                    "Adjusted FeatureLocation to %s" % str(
                        feature.location))
        return feature

    def collect_info_from_features(self, ira_feature, irb_feature):
        # Both fields are "yes" or "no" most of the time. Other cases are
        # exceptions.
        if ira_feature and irb_feature:
            ir_reported = "yes"
        elif not ira_feature and not irb_feature:
            ir_reported = "no"
        else:
            ir_reported = "exception"
        fields = {
            "ACCESSION": self.rec.id,
            "TITLE": self.rec.description,
            "UPDATED": self.rec.annotations.get(
                'date',
                None),
            "IR_REPORTED": ir_reported,
            "IRa_REPORTED": "yes" if ira_feature else "no",
            "IRa_REPORTED_START": ira_feature.location.start +
            1 if ira_feature else None,
            "IRa_REPORTED_END": ira_feature.location.end if ira_feature else None,
            "IRa_REPORTED_LENGTH": int(
                len(ira_feature)) if ira_feature else None,
            "IRb_REPORTED": "yes" if irb_feature else "no",
            "IRb_REPORTED_START": irb_feature.location.start +
            1 if irb_feature else None,
            "IRb_REPORTED_END": irb_feature.location.end if irb_feature else None,
            "IRb_REPORTED_LENGTH": int(
                len(irb_feature)) if irb_feature else None,
        }
        # Forces columns to be integers to avoid any conflicts for null values.
        df = (
            pl.DataFrame([fields])
            .with_columns(pl.col("UPDATED").str.to_datetime("%d-%b-%Y"))
            .cast(
                {
                    "UPDATED": pl.Date,
                    "IRa_REPORTED_START": pl.Int64,
                    "IRa_REPORTED_END": pl.Int64,
                    "IRa_REPORTED_LENGTH": pl.Int64,
                    "IRb_REPORTED_START": pl.Int64,
                    "IRb_REPORTED_END": pl.Int64,
                    "IRb_REPORTED_LENGTH": pl.Int64,
                }
            )
        )
        return df
