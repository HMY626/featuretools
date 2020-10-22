import json

import featuretools as ft


def describe_feature(feature, feature_descriptions=None, primitive_templates=None,
                     metadata_file=None):
    '''Generates an English language description of a feature.

    Args:
        feature (FeatureBase) : Feature to describe
        feature_descriptions (dict, optional) : dictionary mapping features or unique
            feature names to custom descriptions
        primitive_templates (dict, optional) : dictionary mapping primitives or
            primitive names to description templates
        metadata_file (str, optional) : path to metadata json

    Returns:
        str : English description of the feature
    '''
    if not feature_descriptions:
        feature_descriptions = {}
    if not primitive_templates:
        primitive_templates = {}

    if metadata_file:
        file_feature_descriptions, file_primitive_templates = parse_json_metadata(metadata_file)
        feature_descriptions = {**file_feature_descriptions, **feature_descriptions}
        primitive_templates = {**file_primitive_templates, **primitive_templates}

    description = generate_description(feature, feature_descriptions, primitive_templates)
    return description[:1].upper() + description[1:] + '.'


def generate_description(feature,
                         feature_descriptions,
                         primitive_templates):
    # 1) Check if has its own description
    if feature in feature_descriptions or feature.unique_name() in feature_descriptions:
        description = (feature_descriptions.get(feature) or
                       feature_descriptions.get(feature.unique_name()))
        return description

    # 2) Check if identity feature:
    if isinstance(feature, ft.IdentityFeature):
        return 'the "{}"'.format(feature.get_name())

    # 3) Deal with direct features
    if isinstance(feature, ft.DirectFeature):
        base_feature, direct_description = get_direct_description(feature)
        direct_base = generate_description(base_feature,
                                           feature_descriptions,
                                           primitive_templates)
        return direct_base + direct_description

    # Get input descriptions -OR- feature names + adding to list of to explore
    input_descriptions = []
    input_columns = feature.base_features
    if isinstance(feature, ft.feature_base.FeatureOutputSlice):
        input_columns = feature.base_feature.base_features

    for input_col in input_columns:
        col_description = generate_description(input_col,
                                               feature_descriptions,
                                               primitive_templates)
        input_descriptions.append(col_description)

    if isinstance(feature, ft.GroupByTransformFeature):
        groupby_description = input_descriptions.pop()

    # Generate primitive description
    slice_num = None
    template_override = None
    if isinstance(feature, ft.feature_base.FeatureOutputSlice):
        slice_num = feature.n
    if feature.primitive in primitive_templates or feature.primitive.name in primitive_templates:
        template_override = (primitive_templates.get(feature.primitive) or
                             primitive_templates.get(feature.primitive.name))
    primitive_description = feature.primitive.get_description(input_descriptions,
                                                              slice_num=slice_num,
                                                              template_override=template_override)
    if isinstance(feature, ft.feature_base.FeatureOutputSlice):
        feature = feature.base_feature

    # Generate groupby phrase if applicable
    groupby = ''
    if isinstance(feature, ft.AggregationFeature):
        groupby_name = get_aggregation_groupby(feature, feature_descriptions)
        groupby = "for each {}".format(groupby_name)
    elif isinstance(feature, ft.GroupByTransformFeature):
        groupby = "for each {}".format(groupby_description)

    # 6) generate aggregation entity phrase w/ use_previous
    entity_description = ''
    if isinstance(feature, ft.AggregationFeature):
        if feature.use_previous:
            entity_description = "of the previous {} of ".format(feature.use_previous.get_name().lower())
        else:
            entity_description = "of all instances of "
        entity_description += '"{}"'.format(feature.relationship_path[-1][1].child_entity.id)

    # 7) generate where phrase
    where = ''
    if hasattr(feature, 'where') and feature.where:
        where_value = feature.where.primitive.value
        if feature.where in feature_descriptions or feature.where.unique_name() in feature_descriptions:
            where_col = feature_descriptions.get(feature.where) or feature_descriptions.get(feature.where.unique_name())
        else:
            where_col = generate_description(feature.where.base_features[0],
                                             feature_descriptions,
                                             primitive_templates)
        where = 'where {} is {}'.format(where_col, where_value)

    # 8) join all parts of template
    description_template = [primitive_description, entity_description, where, groupby]
    description = " ".join([phrase for phrase in description_template if phrase != ''])

    return description


def get_direct_description(feature):
    direct_description = ' the instance of "{}" associated with this ' \
                         'instance of "{}"'.format(feature.relationship_path[-1][1].parent_entity.id,
                                                   feature.entity_id)
    base_features = feature.base_features
    while isinstance(base_features[0], ft.DirectFeature):
        base_feat = base_features[0]
        base_feat_description = ' the instance of "{}" associated ' \
                                'with'.format(base_feat.relationship_path[-1][1].parent_entity.id)
        direct_description = base_feat_description + direct_description
        base_features = base_feat.base_features
    direct_description = ' of' + direct_description

    return base_features[0], direct_description


def get_aggregation_groupby(feature, feature_descriptions={}):
    groupby_name = feature.entity.index
    groupby_feature = ft.IdentityFeature(feature.entity[groupby_name])
    if groupby_feature in feature_descriptions or groupby_feature.unique_name() in feature_descriptions:
        description = (feature_descriptions.get(groupby_feature) or
                       feature_descriptions.get(groupby_feature.unique_name()))
        if description.startswith('the '):
            return description[4:]
        else:
            return description
    else:
        return '"{}" in "{}"'.format(groupby_name, feature.entity.id)


def parse_json_metadata(file):
    with open(file) as f:
        json_metadata = json.load(f)

    return json_metadata.get('feature_descriptions', {}), json_metadata.get('primitive_templates', {})