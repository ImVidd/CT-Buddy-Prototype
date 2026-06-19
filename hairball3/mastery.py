import json
from collections import Counter
from hairball3.plugin import Plugin

SKILL_POINTS = {
    'Logic': 4, 'FlowControl': 4, 'Synchronization': 4, 'Abstraction': 4,
    'DataRepresentation': 4, 'UserInteractivity': 4, 'Parallelization': 4,
    'MathOperators': 4, 'MotionOperators': 4
}


class Mastery(Plugin):

    def __init__(self, filename, json_project, verbose=False):
        super().__init__(filename, json_project, skill_points=SKILL_POINTS, mode='Extended', verbose=verbose)
        self.possible_scores = {"advanced": 4, "proficient": 3, "developing": 2, "basic": 1}
        self.dict_total_blocks = {}
        self.total_blocks = 0

    def process(self):
        for key, list_info in self.json_project.items():
            if key == "targets":
                for dict_target in list_info:
                    for dicc_key, dicc_value in dict_target.items():
                        if dicc_key == "blocks":
                            for blocks, blocks_value in dicc_value.items():
                                if type(blocks_value) is dict:
                                    self.list_total_blocks.append(blocks_value)
                                    self.dict_total_blocks[blocks] = blocks_value

        if self.list_total_blocks == []:
            raise Exception("No blocks found")

        for block in self.list_total_blocks:
            for key, list_info in block.items():
                if key == "opcode":
                    self.dict_blocks[list_info] += 1
                    self.total_blocks += 1

    def analyze(self):
        self.compute_logic()
        self.compute_flow_control()
        self.compute_synchronization()
        self.compute_abstraction()
        self.compute_data_representation()
        self.compute_user_interactivity()
        self.compute_parallelization()
        self.compute_math_operators()
        self.compute_motion_operators()

    def get_scores(self):
        self.process()
        self.analyze()
        # return simple {dimension: score} dict
        return {dim: vals[0] for dim, vals in self.dict_mastery.items()}

    def set_dimension_score(self, scale_dict, dimension):
        score = 0
        for key, value in scale_dict.items():
            if type(value) == bool and value is True and self.check_lt_max_score(dimension, key):
                if key in self.possible_scores:
                    score = self.possible_scores[key]
                    self.dict_mastery[dimension] = [score, self.skill_points[dimension]]
                    return
        self.dict_mastery[dimension] = [score, self.skill_points[dimension]]

    def check_lt_max_score(self, dimension, level):
        return self.possible_scores[level] <= self.skill_points[dimension]

    def check_list(self, lst):
        return any(item in self.dict_blocks for item in lst)

    def check_more_than_one(self):
        count = sum(1 for b in self.list_total_blocks if b.get('parent') is None)
        return count > 1

    def check_block_sequence(self):
        return any(b['next'] is not None for b in self.dict_total_blocks.values())

    def check_scripts_flag(self, n_scripts):
        return self.dict_blocks['event_whenflagclicked'] >= n_scripts

    def check_scripts_sprite(self, n_scripts):
        return self.dict_blocks['event_whenthisspriteclicked'] >= n_scripts

    def check_scripts_key(self, dict_parall, n_scripts):
        if self.dict_blocks['event_whenkeypressed'] >= n_scripts:
            if dict_parall.get('KEY_OPTION'):
                var_list = set(dict_parall['KEY_OPTION'])
                return any(dict_parall['KEY_OPTION'].count(v) >= n_scripts for v in var_list)
        return False

    def check_scripts_media(self, dict_parall, n_scripts):
        if self.dict_blocks['event_whengreaterthan'] >= n_scripts:
            if dict_parall.get('WHENGREATERTHANMENU'):
                var_list = set(dict_parall['WHENGREATERTHANMENU'])
                return any(dict_parall['WHENGREATERTHANMENU'].count(v) >= n_scripts for v in var_list)
        return False

    def check_scripts_backdrop(self, dict_parall, n_scripts):
        if self.dict_blocks['event_whenbackdropswitchesto'] >= n_scripts:
            if dict_parall.get('BACKDROP'):
                return any(dict_parall['BACKDROP'].count(v) >= n_scripts for v in set(dict_parall['BACKDROP']))
        return False

    def check_scripts_msg(self, dict_parall, n_scripts):
        if self.dict_blocks['event_whenbroadcastreceived'] >= n_scripts:
            if dict_parall.get('BROADCAST_OPTION'):
                return any(dict_parall['BROADCAST_OPTION'].count(v) >= n_scripts for v in set(dict_parall['BROADCAST_OPTION']))
        return False

    def check_scripts_video(self, n_scripts):
        return self.dict_blocks['videoSensing_whenMotionGreaterThan'] >= n_scripts

    def check_scripts(self, n_scripts):
        coincidences = 0
        for block in self.dict_total_blocks.values():
            if block['opcode'] == 'control_if':
                condition = block['inputs'].get('CONDITION')
                if condition:
                    id_condition = condition[1]
                    if id_condition and self.dict_total_blocks.get(id_condition, {}).get('opcode') == 'operator_gt':
                        coincidences += 1
                        if coincidences >= n_scripts:
                            return True
        return False

    def parallelization_dict(self):
        d = {}
        for block in self.list_total_blocks:
            for key, value in block.items():
                if key == 'fields':
                    for k, v in value.items():
                        if k in d:
                            d[k].append(v[0])
                        else:
                            d[k] = v
        return d

    def check_broadcast(self, block):
        return block['opcode'] in {'event_broadcast', 'event_broadcastandwait'}

    def check_conditional(self, block):
        if block['opcode'] == 'control_if':
            return bool(block['inputs'].get('SUBSTACK'))
        if block['opcode'] == 'control_if_else':
            return bool(block['inputs'].get('SUBSTACK')) and bool(block['inputs'].get('SUBSTACK2'))
        return False

    def check_loops(self, block):
        loops = {'control_forever', 'control_repeat', 'control_repeat_until'}
        visited = set()

        def process(b):
            if b is None or b.get('opcode') in visited:
                return
            visited.add(b.get('opcode'))
            if b['opcode'] in loops:
                sub = self.dict_total_blocks.get(b['inputs'].get('SUBSTACK', [None, None])[1])
                while sub:
                    process(sub)
                    sub = self.dict_total_blocks.get(sub.get('next'))

        if block['opcode'] in loops:
            try:
                process(block)
                return len(visited) >= 3
            except KeyError:
                pass
        return False

    def check_advanced_clones(self):
        for block in self.list_total_blocks:
            if block['opcode'] == 'control_start_as_clone':
                nxt = self.dict_total_blocks.get(block['next'])
                while nxt:
                    if self.check_broadcast(nxt) or self.check_loops(nxt) or self.check_conditional(nxt):
                        return True
                    nxt = self.dict_total_blocks.get(nxt['next'])
        return False

    def check_dynamic_msg_handling(self):
        counter = 0
        for block in self.list_total_blocks:
            if block.get('opcode') in {'event_broadcast', 'event_broadcastandwait'}:
                try:
                    msg = block['inputs']['BROADCAST_INPUT'][1][2]
                    if self._has_conditional_or_loop(msg):
                        counter += 1
                except (IndexError, KeyError):
                    pass
        return counter >= 3

    def _has_conditional_or_loop(self, msg):
        for block in self.list_total_blocks:
            if block.get('opcode') == 'event_whenbroadcastreceived' and block['fields']['BROADCAST_OPTION'][1] == msg:
                nxt = self.dict_total_blocks.get(block['next'])
                while nxt:
                    if self.check_conditional(nxt) or self.check_loops(nxt):
                        return True
                    nxt = self.dict_total_blocks.get(nxt['next'])
        return False

    def check_nested_conditionals(self):
        for block in self.dict_total_blocks.values():
            if block.get('opcode') == 'control_if':
                try:
                    sub = self.dict_total_blocks.get(block['inputs']['SUBSTACK'][1])
                    if self._has_nested_conditional(sub):
                        return True
                except KeyError:
                    pass
            elif block.get('opcode') == 'control_if_else':
                try:
                    sub = self.dict_total_blocks.get(block['inputs']['SUBSTACK'][1])
                    sub2 = self.dict_total_blocks.get(block['inputs']['SUBSTACK2'][1])
                    if self._has_nested_conditional(sub) or self._has_nested_conditional(sub2):
                        return True
                except KeyError:
                    pass
        return False

    def _has_nested_conditional(self, substack):
        loops = {'control_forever', 'control_repeat', 'control_repeat_until'}
        while substack:
            if substack.get('opcode') in {'control_if', 'control_if_else'}:
                return True
            if substack.get('opcode') in loops:
                try:
                    loop_sub = self.dict_total_blocks.get(substack['inputs']['SUBSTACK'][1])
                    if self._has_nested_conditional(loop_sub):
                        return True
                except KeyError:
                    pass
            substack = self.dict_total_blocks.get(substack.get('next'))
        return False

    def check_nested_loops(self):
        loops = {'control_forever', 'control_repeat', 'control_repeat_until'}
        for block in self.dict_total_blocks.values():
            if block['opcode'] in loops:
                try:
                    sub = self.dict_total_blocks.get(block['inputs']['SUBSTACK'][1])
                    if self._has_nested_loops(sub):
                        return True
                except KeyError:
                    pass
        return False

    def _has_nested_loops(self, substack):
        loops = {'control_forever', 'control_repeat', 'control_repeat_until'}
        while substack:
            if substack['opcode'] in loops:
                return True
            if substack['opcode'] == 'control_if':
                try:
                    if self._has_nested_loops(self.dict_total_blocks.get(substack['inputs']['SUBSTACK'][1])):
                        return True
                except KeyError:
                    pass
            elif substack['opcode'] == 'control_if_else':
                try:
                    if self._has_nested_loops(self.dict_total_blocks.get(substack['inputs']['SUBSTACK'][1])):
                        return True
                    if self._has_nested_loops(self.dict_total_blocks.get(substack['inputs']['SUBSTACK2'][1])):
                        return True
                except KeyError:
                    pass
            substack = self.dict_total_blocks.get(substack.get('next'))
        return False

    def check_formula(self):
        operators = {'operator_add', 'operator_subtract', 'operator_multiply',
                     'operator_divide', 'operator_mathop', 'operator_random'}
        for block in self.list_total_blocks:
            if block['opcode'] in operators:
                if self._count_nested_operators(block, operators) >= 1:
                    return True
        return False

    def _count_nested_operators(self, block, operators):
        count = 0
        for _, value in block['inputs'].items():
            for v in value:
                if isinstance(v, str) and v in self.dict_total_blocks:
                    connected = self.dict_total_blocks[v]
                    if connected['opcode'] in operators:
                        count += 1
                        count += self._count_nested_operators(connected, operators)
        return count

    def check_trigonometry(self):
        trig = {'cos', 'sin', 'tan', 'asin', 'acos', 'atan'}
        for block in self.list_total_blocks:
            if block['opcode'] == 'operator_mathop':
                if any(e in trig for e in block['fields']['OPERATOR']):
                    return True
        return False

    def check_motion_complex_sequences(self):
        motion = {'motion_movesteps', 'motion_gotoxy', 'motion_glidesecstoxy', 'motion_glideto',
                  'motion_setx', 'motion_sety', 'motion_changexby', 'motion_changeyby',
                  'motion_pointindirection', 'motion_pointtowards', 'motion_turnright', 'motion_turnleft',
                  'motion_goto', 'motion_ifonedgebounce', 'motion_setrotationstyles'}
        counter = 0
        for value in self.dict_total_blocks.values():
            if value.get('parent') is None:
                counter = 0
            elif value.get('opcode') in motion:
                counter += 1
                if counter >= 5:
                    return True
        return False

    def _check_mouse(self):
        for block in self.list_total_blocks:
            for key, value in block.items():
                if key == 'fields':
                    for mk, mv in value.items():
                        if mk in ('TO', 'TOUCHINGOBJECTMENU') and mv[0] == '_mouse_':
                            return 1
        return 0

    def check_mouse_blocks(self):
        if self.dict_blocks['motion_goto_menu'] or self.dict_blocks['sensing_touchingobjectmenu']:
            return self._check_mouse() == 1
        return False

    def check_ui_developing(self):
        developing = {'event_whenkeypressed', 'event_whenthisspriteclicked', 'sensing_mousedown',
                      'sensing_keypressed', 'sensing_askandwait', 'sensing_answer'}
        return self.check_list(developing) or self.check_mouse_blocks()

    def check_ui_proficiency(self):
        proficiency = {'videoSensing_videoToggle', 'videoSensing_videoOn', 'videoSensing_whenMotionGreaterThan',
                       'videoSensing_setVideoTransparency', 'sensing_loudness'}
        return self.check_list(proficiency) or self.check_scripts(n_scripts=2)

    def check_ui_advanced(self):
        non_controllers = ['music', 'pen', 'videoSensing', 'text2speech', 'translate', 'learningmlTexts', 'learningmlImages']
        extensions = self.json_project.get('extensions', [])
        return any(e not in non_controllers for e in extensions)

    def check_p_advanced(self, d):
        return (self.check_scripts(3) or self.check_scripts_media(d, 3) or self.check_scripts_backdrop(d, 3)
                or self.check_scripts_msg(d, 3) or self.check_scripts_video(3))

    def check_p_proficiency(self, d):
        return (self.check_scripts(2) or self.check_scripts_media(d, 2) or self.check_scripts_backdrop(d, 2)
                or self.check_list({'control_create_clone_of'}) or self.check_scripts_msg(d, 2) or self.check_scripts_video(2))

    def check_p_developing(self, d):
        return self.check_scripts_key(d, 2) or self.check_scripts_sprite(2)

    # --- compute methods ---

    def compute_logic(self):
        scale_dict = {
            "advanced": self.check_nested_conditionals(),
            "proficient": self.check_list({'operator_and', 'operator_or', 'operator_not'}),
            "developing": self.check_list({'control_if_else'}),
            "basic": self.check_list({'control_if'})
        }
        self.set_dimension_score(scale_dict, "Logic")

    def compute_flow_control(self):
        scale_dict = {
            "advanced": self.check_nested_loops(),
            "proficient": self.check_list({'control_repeat_until'}),
            "developing": self.check_list({'control_repeat', 'control_forever'}),
            "basic": self.check_block_sequence()
        }
        self.set_dimension_score(scale_dict, "FlowControl")

    def compute_synchronization(self):
        scale_dict = {
            "advanced": self.check_dynamic_msg_handling(),
            "proficient": self.check_list({'control_wait_until', 'event_whenbackdropswitchesto', 'event_broadcastandwait'}),
            "developing": self.check_list({'event_broadcast', 'event_whenbroadcastreceived', 'control_stop'}),
            "basic": self.check_list({'control_wait'})
        }
        self.set_dimension_score(scale_dict, "Synchronization")

    def compute_abstraction(self):
        scale_dict = {
            "advanced": self.check_advanced_clones(),
            "proficient": self.check_list({'procedures_definition'}),
            "developing": self.check_list({'control_start_as_clone'}),
            "basic": self.check_more_than_one()
        }
        self.set_dimension_score(scale_dict, "Abstraction")

    def compute_data_representation(self):
        scale_dict = {
            "advanced": self.check_list({'operator_equals', 'operator_gt', 'operator_and', 'operator_or', 'operator_not', 'operator_lt'}),
            "proficient": self.check_list({'data_lengthoflist', 'data_showlist', 'data_insertatlist', 'data_deleteoflist',
                                           'data_addtolist', 'data_replaceitemoflist', 'data_listcontainsitem', 'data_hidelist', 'data_itemoflist'}),
            "developing": self.check_list({'data_changevariableby', 'data_setvariableto'}),
            "basic": self.check_list({'motion_movesteps', 'motion_gotoxy', 'motion_glidesecstoxy', 'motion_setx', 'motion_sety',
                                      'motion_changexby', 'motion_changeyby', 'looks_changesizeby', 'looks_setsizeto'})
        }
        self.set_dimension_score(scale_dict, "DataRepresentation")

    def compute_user_interactivity(self):
        scale_dict = {
            "advanced": self.check_ui_advanced(),
            "proficient": self.check_ui_proficiency(),
            "developing": self.check_ui_developing(),
            "basic": self.check_list({'event_whenflagclicked'})
        }
        self.set_dimension_score(scale_dict, "UserInteractivity")

    def compute_parallelization(self):
        d = self.parallelization_dict()
        scale_dict = {
            "advanced": self.check_p_advanced(d),
            "proficient": self.check_p_proficiency(d),
            "developing": self.check_p_developing(d),
            "basic": self.check_scripts_flag(2)
        }
        self.set_dimension_score(scale_dict, "Parallelization")

    def compute_math_operators(self):
        scale_dict = {
            "advanced": self.check_trigonometry(),
            "proficient": self.check_list({'operator_join', 'operator_letter_of', 'operator_length', 'operator_contains'}),
            "developing": self.check_formula(),
            "basic": self.check_list({'operator_add', 'operator_subtract', 'operator_multiply', 'operator_divide'})
        }
        self.set_dimension_score(scale_dict, "MathOperators")

    def compute_motion_operators(self):
        scale_dict = {
            "advanced": self.check_motion_complex_sequences(),
            "proficient": self.check_list({'motion_glideto', 'motion_glidesecstoxy'}),
            "developing": self.check_list({'motion_turnleft', 'motion_turnright', 'motion_setrotationstyles',
                                           'motion_pointindirection', 'motion_pointtowards'}),
            "basic": self.check_list({'motion_movesteps', 'motion_gotoxy', 'motion_changexby',
                                      'motion_goto', 'motion_changeyby', 'motion_setx', 'motion_sety'})
        }
        self.set_dimension_score(scale_dict, "MotionOperators")
