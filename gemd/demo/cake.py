"""Bake a cake."""
import json

import random

from gemd.entity.attribute import Condition, Parameter, Property, PropertyAndConditions
from gemd.entity.bounds import IntegerBounds, RealBounds, CategoricalBounds, CompositionBounds, \
    MolecularStructureBounds
from gemd.entity.object import ProcessSpec, ProcessRun, MaterialSpec, MaterialRun, \
    MeasurementSpec, MeasurementRun, IngredientSpec, IngredientRun
from gemd.entity.template import ProcessTemplate, MaterialTemplate, MeasurementTemplate, \
    PropertyTemplate, ParameterTemplate, ConditionTemplate
from gemd.entity.value import NominalInteger, UniformInteger, \
    NominalReal, NormalReal, UniformReal, \
    NominalCategorical, DiscreteCategorical, \
    NominalComposition, EmpiricalFormula, \
    Smiles, InChI
from gemd.enumeration.origin import Origin

from gemd.entity.util import complete_material_history, make_instance
from gemd.entity.file_link import FileLink
from gemd.entity.source.performed_source import PerformedSource
from gemd.json import GEMDJson

from gemd.util.impl import recursive_foreach


# For now, module constant, though likely this should get promoted to a package level
DEMO_SCOPE = 'citrine-demo'
TEMPLATE_SCOPE = DEMO_SCOPE + '-template'


def change_scope(data, *, templates=None):
    """
    Change scope(s) of internal uids.

    Parameters
    ----------
    data: str
        Scope for the Run and Spec objects
    templates: str, optional
        Scope for the Attribute Templates and Object Templates.  If `None`,
        will be set to `data + '-template'`

    """
    global DEMO_SCOPE, TEMPLATE_SCOPE
    DEMO_SCOPE = data
    if templates is None:
        TEMPLATE_SCOPE = DEMO_SCOPE + '-template'
    else:
        TEMPLATE_SCOPE = templates


def import_toothpick_picture():
    """Return the stream of the toothpick picture."""
    import pkg_resources
    resource = pkg_resources.resource_stream("gemd.demo", "toothpick.jpg")

    return resource


def make_cake_templates():
    """Define all templates independently, as in the wild this will be an independent operation."""
    tmpl = dict()

    # Attributes
    tmpl["Mixer speed setting"] = ParameterTemplate(
        name="Mixer speed setting",
        description="What speed setting to use on the mixer",
        bounds=IntegerBounds(0, 10)
    )

    tmpl['Cooking time'] = ConditionTemplate(
        name="Cooking time",
        description="The time elapsed during a cooking process",
        bounds=RealBounds(0, 7 * 24.0, "hr")
    )
    tmpl["Oven temperature setting"] = ParameterTemplate(
        name="Oven temperature setting",
        description="Where the knob points",
        bounds=RealBounds(0, 2000.0, "K")
    )
    tmpl["Oven temperature"] = ConditionTemplate(
        name="Oven temperature",
        description="Actual temperature measured by the thermocouple",
        bounds=RealBounds(0, 2000.0, "K")
    )

    tmpl["Toothpick test"] = PropertyTemplate(
        name="Toothpick test",
        description="Results of inserting a toothpick to check doneness",
        bounds=CategoricalBounds(["wet", "crumbs", "completely clean"])
    )
    tmpl["Color"] = PropertyTemplate(
        name="Baked color",
        description="Visual observation of the color of a baked good",
        bounds=CategoricalBounds(["Pale", "Golden brown", "Deep brown", "Black"])
    )

    tmpl["Tastiness"] = PropertyTemplate(
        name="Tastiness",
        description="Yumminess on a fairly arbitrary scale",
        bounds=IntegerBounds(lower_bound=1, upper_bound=10)
    )

    tmpl["Nutritional Information"] = PropertyTemplate(
        name="Nutritional Information",
        description="FDA Nutrition Facts, mass basis.  Please be attentive to g vs. mg.  "
                    "`other-carbohydrate` and `other-fat` are the total values minus the "
                    "broken-out quantities. Other is the difference between the total and the "
                    "serving size.",
        bounds=CompositionBounds(
            components=[
                'other',
                'saturated-fat',
                'trans-fat',
                'other-fat',
                'cholesterol',
                'sodium',
                'dietary-fiber',
                'sugars',
                'other-carbohydrate',
                'protein',
                'vitamin-d',
                'calcium',
                'iron',
                'potassium'
            ]
        )
    )
    tmpl["Sample Mass"] = ConditionTemplate(
        name="Sample Mass",
        description="Sample size in mass units, to go along with FDA Nutrition Facts",
        bounds=RealBounds(1.e-3, 1.e4, "g")
    )
    tmpl["Expected Sample Mass"] = ParameterTemplate(
        name="Expected Sample Mass",
        description="Specified sample size in mass units, to go along with FDA Nutrition Facts",
        bounds=RealBounds(1.e-3, 1.e4, "g")
    )
    tmpl["Chemical Formula"] = PropertyTemplate(
        name="Chemical Formula",
        description="The chemical formula of a material",
        bounds=CompositionBounds(components=EmpiricalFormula.all_elements())
    )
    tmpl["Molecular Structure"] = PropertyTemplate(
        name="Molecular Structure",
        description="The molecular structure of the material",
        bounds=MolecularStructureBounds()
    )

    # Objects
    tmpl["Procuring"] = ProcessTemplate(
        name="Procuring",
        description="Buyin' stuff"
    )
    tmpl["Baking"] = ProcessTemplate(
        name="Baking",
        description='Using heat to promote chemical reactions in a material',
        allowed_labels=['precursor'],
        conditions=[(tmpl["Oven temperature"], RealBounds(0, 700, "degF"))],
        parameters=[(tmpl["Oven temperature setting"], RealBounds(100, 550, "degF"))]
    )
    tmpl["Icing"] = ProcessTemplate(
        name="Icing",
        description='Applying a coating to a substrate',
        allowed_labels=['coating', 'substrate']
    )
    tmpl["Mixing"] = ProcessTemplate(
        name="Mixing",
        description='Physically combining ingredients',
        allowed_labels=['wet', 'dry', 'leavening', 'seasoning',
                        'sweetener', 'shortening', 'flavoring'],
        parameters=[tmpl["Mixer speed setting"]]
    )

    tmpl["Generic Material"] = MaterialTemplate(name="Generic")
    tmpl["Nutritional Material"] = MaterialTemplate(
        name="Nutritional Material",
        description="A material with FDA Nutrition Facts attached",
        properties=[
            tmpl["Nutritional Information"]
        ]
    )
    tmpl["Formulaic Material"] = MaterialTemplate(
        name="Formulaic Material",
        description="A material with chemical characterization",
        properties=[
            tmpl["Chemical Formula"],
            tmpl["Molecular Structure"]
        ]
    )
    tmpl["Baked Good"] = MaterialTemplate(
        name="Baked Good",
        properties=[tmpl["Toothpick test"], tmpl["Color"]]
    )
    tmpl["Dessert"] = MaterialTemplate(
        name="Dessert",
        properties=[tmpl["Tastiness"]]
    )

    tmpl["Doneness"] = MeasurementTemplate(
        name="Doneness test",
        description="An ensemble of tests to determine the doneness of a baked good",
        properties=[tmpl["Toothpick test"], tmpl["Color"]]
    )
    tmpl["Taste test"] = MeasurementTemplate(
        name="Taste test",
        properties=[tmpl["Tastiness"]]
    )
    tmpl["Nutritional Analysis"] = MeasurementTemplate(
        name="Nutritional Analysis",
        properties=[tmpl["Nutritional Information"]],
        conditions=[tmpl["Sample Mass"]],
        parameters=[tmpl["Expected Sample Mass"]]
    )
    tmpl["Elemental Analysis"] = MeasurementTemplate(
        name="Elemental Analysis",
        properties=[tmpl["Chemical Formula"]],
        conditions=[tmpl["Sample Mass"]],
        parameters=[tmpl["Expected Sample Mass"]]
    )

    for key in tmpl:
        tmpl[key].add_uid(TEMPLATE_SCOPE, key)
    return tmpl


def make_cake_spec(tmpl=None):
    """Define a recipe for making a cake."""
    ###############################################################################################
    # Templates
    if tmpl is None:
        tmpl = make_cake_templates()

    def _ingredient_kwargs(material):
        """Convenience method to utilize material fields in creating an ingredient's arguments."""
        return {
            "name": material.name.lower(),
            "tags": list(material.tags),
            "material": material
        }

    def _material_kwargs(material_name, process_tmpl_name, process_kwargs):
        """Convenience method to reuse material name in creating a material's arguments."""
        return {
            "name": material_name,
            "process": ProcessSpec(
                name="{} {}".format(process_tmpl_name, material_name),
                template=tmpl[process_tmpl_name],
                **process_kwargs
            ),
        }

    ###############################################################################################
    # Objects
    cake = MaterialSpec(
        **_material_kwargs(
            material_name="Cake",
            process_tmpl_name="Icing",
            process_kwargs={
                "tags": ['spreading'],
                "notes": 'The act of covering a baked output with frosting'
            }
        ),
        template=tmpl["Dessert"],
        properties=[
            PropertyAndConditions(Property(name="Tastiness",
                                           value=NominalInteger(5),
                                           template=tmpl["Tastiness"],
                                           origin="specified"
                                           ))
        ],
        file_links=FileLink(
            filename="Becky's Butter Cake",
            url='https://www.landolakes.com/recipe/16730/becky-s-butter-cake/'
        ),
        tags=[
            'cake::butter cake',
            'dessert::baked::cake',
            'iced::chocolate'
        ],
        notes='Butter cake recipe reminiscent of the 1-2-3-4 cake that Grandma may have baked.'
    )

    ########################
    frosting = MaterialSpec(
        **_material_kwargs(
            material_name="Frosting",
            process_tmpl_name="Mixing",
            process_kwargs={
                "tags": [
                    'mixing'
                ],
                "parameters": [
                    Parameter(name='Mixer speed setting',
                              template=tmpl['Mixer speed setting'],
                              origin='specified',
                              value=NominalInteger(2))
                ],
                "notes": 'Combining ingredients to make a sweet frosting'
            }
        ),
        template=tmpl["Dessert"],
        tags=[
            'frosting::chocolate',
            'topping::chocolate'
        ],
        notes='Chocolate frosting'
    )
    IngredientSpec(
        **_ingredient_kwargs(frosting),
        notes='Seems like a lot of frosting',
        labels=['coating'],
        process=cake.process,
        absolute_quantity=NominalReal(nominal=0.751, units='kg')
    )

    baked_cake = MaterialSpec(
        **_material_kwargs(
            material_name="Baked Cake",
            process_tmpl_name="Baking",
            process_kwargs={
                "tags": [
                    'oven::baking'
                ],
                "conditions": [
                    Condition(name='Cooking time',
                              template=tmpl['Cooking time'],
                              origin=Origin.SPECIFIED,
                              value=NormalReal(mean=50, std=5, units='min'))
                ],
                "parameters": [
                    Parameter(name='Oven temperature setting',
                              template=tmpl['Oven temperature setting'],
                              origin="specified",
                              value=NominalReal(nominal=350, units='degF'))
                ],
                "notes": 'Using heat to convert batter into a solid matrix'
            }
        ),
        template=tmpl["Baked Good"],
        properties=[
            PropertyAndConditions(
                property=Property(
                    name="Toothpick test",
                    value=NominalCategorical("completely clean"),
                    template=tmpl["Toothpick test"]
                )
            ),
            PropertyAndConditions(
                property=Property(
                    name="Color",
                    value=NominalCategorical("Golden brown"),
                    template=tmpl["Color"],
                    origin="specified"
                )
            )
        ],
        tags=[
            'substrate'
        ],
        notes='The cakey part of the cake'
    )
    IngredientSpec(
        **_ingredient_kwargs(baked_cake),
        labels=['substrate'],
        process=cake.process
    )

    ########################
    batter = MaterialSpec(
        **_material_kwargs(
            material_name="Batter",
            process_tmpl_name="Mixing",
            process_kwargs={
                "tags": [
                    'mixing'
                ],
                "parameters": [
                    Parameter(name='Mixer speed setting',
                              template=tmpl['Mixer speed setting'],
                              origin='specified',
                              value=NominalInteger(2))
                ],
                "notes": 'Combining ingredients to make a baking feedstock'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'mixture'
        ],
        notes='The fluid that converts to cake with heat'
    )
    IngredientSpec(
        **_ingredient_kwargs(batter),
        labels=['precursor'],
        process=baked_cake.process
    )

    ########################
    wetmix = MaterialSpec(
        **_material_kwargs(
            material_name="Wet Ingredients",
            process_tmpl_name="Mixing",
            process_kwargs={
                "tags": [
                    'mixing'
                ],
                "parameters": [
                    Parameter(name='Mixer speed setting',
                              template=tmpl['Mixer speed setting'],
                              origin='specified',
                              value=NominalInteger(2))
                ],
                "notes": 'Combining wet ingredients to make a baking feedstock'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            "mixture"
        ],
        notes='The wet fraction of a batter'
    )
    IngredientSpec(
        **_ingredient_kwargs(wetmix),
        labels=['wet'],
        process=batter.process
    )

    drymix = MaterialSpec(
        **_material_kwargs(
            material_name="Dry Ingredients",
            process_tmpl_name="Mixing",
            process_kwargs={
                "tags": [
                    'mixing'
                ],
                "notes": 'Combining dry ingredients to make a baking feedstock'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            "mixture"
        ],
        notes='The dry fraction of a batter'
    )
    IngredientSpec(
        **_ingredient_kwargs(drymix),
        labels=['dry'],
        process=batter.process,
        absolute_quantity=NominalReal(nominal=3.052, units='cups')
    )

    ########################
    flour = MaterialSpec(
        **_material_kwargs(
            material_name="Flour",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::dry-goods'
                ],
                "notes": 'Purchasing all purpose flour'
            }
        ),
        template=tmpl["Nutritional Material"],
        properties=[
            PropertyAndConditions(
                property=Property(
                    name="Nutritional Information",
                    value=NominalComposition(
                        {
                            "dietary-fiber": 1,
                            "sugars": 1,
                            "other-carbohydrate": 20,
                            "protein": 4,
                            "other": 4
                        }
                    ),
                    template=tmpl["Nutritional Information"],
                    origin="specified"
                ),
                conditions=Condition(
                    name="Serving Size",
                    value=NominalReal(30, 'g'),
                    template=tmpl["Sample Mass"],
                    origin="specified"
                )
            )
        ],
        tags=[
            'raw material',
            'flour',
            'dry-goods'
        ],
        notes='All-purpose flour'
    )
    IngredientSpec(
        **_ingredient_kwargs(flour),
        labels=['dry'],
        process=drymix.process,
        volume_fraction=NominalReal(nominal=0.9829, units='')  # 3 cups
    )

    baking_powder = MaterialSpec(
        **_material_kwargs(
            material_name="Baking Powder",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::dry-goods'
                ],
                "notes": 'Purchasing baking powder'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material',
            'levening',
            'dry-goods'
        ],
        notes='Leavening agent for cake'
    )
    IngredientSpec(
        **_ingredient_kwargs(baking_powder),
        labels=['leavening', 'dry'],
        process=drymix.process,
        volume_fraction=NominalReal(nominal=0.0137, units='')  # 2 teaspoons
    )

    salt = MaterialSpec(
        **_material_kwargs(
            material_name="Salt",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::dry-goods'
                ],
                "notes": 'Purchasing salt'
            }
        ),
        template=tmpl["Formulaic Material"],
        tags=[
            'raw material',
            'seasoning',
            'dry-goods'
        ],
        notes='Plain old NaCl',
        properties=[
            PropertyAndConditions(Property(name='Formula', value=EmpiricalFormula("NaCl")))
        ]
    )
    IngredientSpec(
        **_ingredient_kwargs(salt),
        labels=['dry', 'seasoning'],
        process=drymix.process,
        volume_fraction=NominalReal(nominal=0.0034, units='')  # 1/2 teaspoon
    )

    sugar = MaterialSpec(
        **_material_kwargs(
            material_name="Sugar",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::dry-goods'
                ],
                "notes": 'Purchasing all purpose flour'
            }
        ),
        template=tmpl["Formulaic Material"],
        tags=[
            'raw material',
            'sweetener',
            'dry-goods'
        ],
        notes='Sugar',
        properties=[
            PropertyAndConditions(Property(name="Formula", value=EmpiricalFormula("C12H22O11"))),
            PropertyAndConditions(
                Property(name='SMILES',
                         value=Smiles("C(C1C(C(C(C(O1)OC2(C(C(C(O2)CO)O)O)CO)O)O)O)O"),
                         template=tmpl["Molecular Structure"]
                         )
            )
        ]
    )
    IngredientSpec(
        **_ingredient_kwargs(sugar),
        labels=['wet', 'sweetener'],
        process=wetmix.process,
        absolute_quantity=NominalReal(nominal=2, units='cups')
    )

    butter = MaterialSpec(
        **_material_kwargs(
            material_name="Butter",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::produce'
                ],
                "notes": 'Purchasing butter'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material',
            'produce',
            'shortening',
            'dairy'
        ],
        notes='Shortening for making rich, buttery baked goods'
    )
    IngredientSpec(
        **_ingredient_kwargs(butter),
        labels=['wet', 'shortening'],
        process=wetmix.process,
        absolute_quantity=NominalReal(nominal=1, units='cups')
    )
    IngredientSpec(
        **_ingredient_kwargs(butter),
        labels=['shortening'],
        process=frosting.process,
        mass_fraction=NominalReal(nominal=0.1434, units='')  # 1/2 c @ 0.911 g/cc
    )

    eggs = MaterialSpec(
        **_material_kwargs(
            material_name="Eggs",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::produce'
                ],
                "notes": 'Purchasing eggs'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material',
            'produce',
        ],
        notes='A custard waiting to happen'
    )
    IngredientSpec(
        **_ingredient_kwargs(eggs),
        labels=['wet'],
        absolute_quantity=NominalReal(nominal=4, units='')
    )

    vanilla = MaterialSpec(
        **_material_kwargs(
            material_name="Vanilla",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::solution'
                ],
                "notes": 'Purchasing vanilla'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material',
            'seasoning'
        ],
        notes='Vanilla Extract is mostly alcohol but the most important component '
              'is vanillin (see attached structure)',
        properties=[
            PropertyAndConditions(
                Property(name='Component Structure',
                         value=InChI("InChI=1S/C8H8O3/c1-11-8-4-6(5-9)2-3-7(8)10/h2-5,10H,1H3"),
                         template=tmpl["Molecular Structure"]
                         )
            )
        ]
    )
    IngredientSpec(
        **_ingredient_kwargs(vanilla),
        labels=['wet', 'flavoring'],
        process=wetmix.process,
        absolute_quantity=NominalReal(nominal=2, units='teaspoons')
    )
    IngredientSpec(
        **_ingredient_kwargs(vanilla),
        labels=['flavoring'],
        process=frosting.process,
        mass_fraction=NominalReal(nominal=0.0231, units='')  # 2 tsp @ 0.879 g/cc
    )

    milk = MaterialSpec(
        **_material_kwargs(
            material_name="Milk",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::produce'
                ],
                "notes": 'Purchasing milk'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material',
            'produce',
            'dairy'
        ],
        notes=''
    )
    IngredientSpec(
        **_ingredient_kwargs(milk),
        labels=['wet'],
        process=batter.process,
        absolute_quantity=NominalReal(nominal=1, units='cup')
    )
    IngredientSpec(
        **_ingredient_kwargs(milk),
        labels=[],
        process=frosting.process,
        mass_fraction=NominalReal(nominal=0.0816, units='')  # 1/4 c @ 1.037 g/cc
    )

    chocolate = MaterialSpec(
        **_material_kwargs(
            material_name="Chocolate",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::dry-goods'
                ],
                "notes": 'Purchasing chocolate'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material'
        ],
        notes=''
    )
    IngredientSpec(
        **_ingredient_kwargs(chocolate),
        labels=['flavoring'],
        process=frosting.process,
        mass_fraction=NominalReal(nominal=0.1132, units='')  # 3 oz.
    )

    powder_sugar = MaterialSpec(
        **_material_kwargs(
            material_name="Powdered Sugar",
            process_tmpl_name="Procuring",
            process_kwargs={
                "tags": [
                    'purchase::dry-goods'
                ],
                "notes": 'Purchasing powdered sugar'
            }
        ),
        template=tmpl["Generic Material"],
        tags=[
            'raw material',
            'sweetener',
            'dry-goods'
        ],
        notes='Granulated sugar mixed with corn starch'
    )
    IngredientSpec(
        **_ingredient_kwargs(powder_sugar),
        labels=['flavoring'],
        process=frosting.process,
        mass_fraction=NominalReal(nominal=0.6387, units='')  # 4 c @ 30 g/ 0.25 cups
    )

    # Crawl tree and annotate with uids; only add ids if there's nothing there
    def _make_fuzzer():
        """Generate closure that knows if it's seen a given name."""
        seen = set()

        def _fuzz_func(obj):
            """Add fuzz to name in ID as necessary."""
            name = 'ing-' if isinstance(obj, IngredientSpec) else ''
            name += obj.name
            while name.lower() in seen:
                name += '-again'
            seen.add(name.lower())
            return name

        return _fuzz_func

    _name_fuzz = _make_fuzzer()
    recursive_foreach(cake, lambda obj: obj.uids or obj.add_uid(DEMO_SCOPE, _name_fuzz(obj)))

    return cake


def make_cake(seed=None, tmpl=None, cake_spec=None, toothpick_img=None):
    """Define all objects that go into making a demo cake."""
    import struct
    import hashlib

    if seed is not None:
        random.seed(seed)
    ######################################################################
    # Parent Objects
    if tmpl is None:
        tmpl = make_cake_templates()
    if cake_spec is None:
        cake_spec = make_cake_spec(tmpl)

    ######################################################################
    # Objects
    cake = make_instance(cake_spec)
    operators = ['gwash', 'jadams', 'thomasj', 'jmadison', 'jmonroe']
    producers = ['Fresh Farm', 'Sunnydale', 'Greenbrook']
    drygoods = ['Acme', 'A1', 'Reliable', "Big Box"]
    cake.process.source = PerformedSource(performed_by=random.choice(operators),
                                          performed_date='2015-03-14')
    # Replace Abstract/In General
    queue = [cake]
    while queue:
        item = queue.pop(0)
        if item.spec.tags is not None:
            item.tags = list(item.spec.tags)
        if item.spec.notes:  # Neither None or empty string
            item.notes = 'The spec says "{}"'.format(item.spec.notes)
        if isinstance(item, MaterialRun):
            if 'raw material' in item.tags:
                if 'produce' in item.tags:
                    supplier = random.choice(producers)
                else:
                    supplier = random.choice(drygoods)
                item.name = "{} {}".format(supplier, item.spec.name)
            queue.append(item.process)
        elif isinstance(item, ProcessRun):
            queue.extend(item.ingredients)
            if item.template.name == "Procuring":
                item.source = PerformedSource(performed_by='hamilton',
                                              performed_date='2015-02-17')
                item.name = "{} {}".format(item.template.name, item.output_material.name)
            else:
                item.source = cake.process.source
        elif isinstance(item, IngredientRun):
            queue.append(item.material)
            fuzz = 0.95 + 0.1 * random.random()
            if item.spec.absolute_quantity is not None:
                item.absolute_quantity = \
                    NormalReal(mean=fuzz * item.spec.absolute_quantity.nominal,
                               std=0.05 * item.spec.absolute_quantity.nominal,
                               units=item.spec.absolute_quantity.units)
            if item.spec.volume_fraction is not None:
                # The only element here is dry mix, and it's almost entirely flour
                item.volume_fraction = \
                    NormalReal(mean=0.01 * (fuzz - 0.5) + item.spec.volume_fraction.nominal,
                               std=0.005,
                               units=item.spec.volume_fraction.units)
            if item.spec.mass_fraction is not None:
                item.mass_fraction = \
                    UniformReal(lower_bound=(fuzz - 0.05) * item.spec.mass_fraction.nominal,
                                upper_bound=(fuzz + 0.05) * item.spec.mass_fraction.nominal,
                                units=item.spec.mass_fraction.units)
            if item.spec.number_fraction is not None:
                item.number_fraction = \
                    NormalReal(mean=fuzz * item.spec.number_fraction.nominal,
                               std=0.05 * item.spec.number_fraction.nominal,
                               units=item.spec.number_fraction.units)

        else:
            raise TypeError("Unexpected object in the queue")

    frosting = \
        next(x.material for x in cake.process.ingredients if 'rosting' in x.name)
    baked = \
        next(x.material for x in cake.process.ingredients if 'aked' in x.name)

    def _find_name(name, material):
        """Recursively search for the right material."""
        if name in material.name:
            return material
        for ingredient in material.process.ingredients:
            result = _find_name(name, ingredient.material)
            if result:
                return result
        return

    flour = _find_name('Flour', cake)
    salt = _find_name('Salt', cake)
    sugar = _find_name('Sugar', cake)

    # Add measurements
    cake_taste = MeasurementRun(name='Final Taste', material=cake)
    cake_appearance = MeasurementRun(name='Final Appearance', material=cake)
    frosting_taste = MeasurementRun(name='Frosting Taste', material=frosting)
    frosting_sweetness = MeasurementRun(name='Frosting Sweetness', material=frosting)
    baked_doneness = MeasurementRun(name='Baking doneness', material=baked)
    flour_content = MeasurementRun(name='Flour nutritional analysis', material=flour)
    salt_content = MeasurementRun(name='Salt elemental analysis', material=salt)
    sugar_content = MeasurementRun(name='Sugar elemental analysis', material=sugar)

    if toothpick_img is not None:
        baked_doneness.file_links.append(toothpick_img)

    # and spec out the measurements
    cake_taste.spec = MeasurementSpec(name='Taste', template=tmpl['Taste test'])
    cake_appearance.spec = MeasurementSpec(name='Appearance')
    frosting_taste.spec = cake_taste.spec  # Taste
    frosting_sweetness.spec = MeasurementSpec(name='Sweetness')
    baked_doneness.spec = MeasurementSpec(name='Doneness', template=tmpl["Doneness"])
    flour_content.spec = MeasurementSpec(name='Nutritional analysis',
                                         template=tmpl["Nutritional Analysis"])
    salt_content.spec = MeasurementSpec(name='Elemental analysis',
                                        template=tmpl["Elemental Analysis"]
                                        )
    sugar_content.spec = salt_content.spec

    for msr in (cake_taste, cake_appearance, frosting_taste, frosting_sweetness,
                baked_doneness, flour_content, salt_content, sugar_content):
        msr.spec.add_uid(DEMO_SCOPE, msr.spec.name)

    ######################################################################
    # Let's add some attributes
    baked.process.conditions.append(Condition(name='Cooking time',
                                              template=tmpl['Cooking time'],
                                              origin=Origin.MEASURED,
                                              value=NominalReal(nominal=48, units='min')))
    baked.process.conditions.append(Condition(name='Oven temperature',
                                              origin="measured",
                                              value=NominalReal(nominal=362, units='degF')))

    cake_taste.properties.append(Property(name='Tastiness',
                                          origin=Origin.MEASURED,
                                          template=tmpl['Tastiness'],
                                          value=UniformInteger(4, 5)))
    cake_appearance.properties.append(Property(name='Visual Appeal',
                                               origin=Origin.MEASURED,
                                               value=NominalInteger(nominal=5)))
    frosting_taste.properties.append(Property(name='Tastiness',
                                              origin=Origin.MEASURED,
                                              template=tmpl['Tastiness'],
                                              value=NominalInteger(nominal=4)))
    frosting_sweetness.properties.append(Property(name='Sweetness (Sucrose-basis)',
                                                  origin=Origin.MEASURED,
                                                  value=NominalReal(nominal=1.7, units='')))

    baked_doneness.properties.append(Property(
        name='Toothpick test',
        origin="measured",
        template=tmpl["Toothpick test"],
        value=NominalCategorical("crumbs")
    ))
    baked_doneness.properties.append(Property(
        name='Color',
        origin="measured",
        template=tmpl["Color"],
        value=DiscreteCategorical({
            "Pale": 0.05,
            "Golden brown": 0.65,
            "Deep brown": 0.3
        })
    ))

    flour_content.properties.append(Property(
        name='Nutritional Information',
        value=NominalComposition(
            {
                "dietary-fiber": 1 * (0.99 + 0.02 * random.random()),
                "sugars": 1 * (0.99 + 0.02 * random.random()),
                "other-carbohydrate": 20 * (0.99 + 0.02 * random.random()),
                "protein": 4 * (0.99 + 0.02 * random.random()),
                "other": 4 * (0.99 + 0.02 * random.random())
            }
        ),
        template=tmpl["Nutritional Information"],
        origin="measured"
    ))
    flour_content.conditions.append(Condition(
        name='Sample Mass',
        value=NormalReal(
            mean=99 + 2 * random.random(),
            std=1.5,
            units='mg'
        ),
        template=tmpl["Sample Mass"],
        origin="measured"
    ))
    flour_content.parameters.append(Parameter(
        name='Expected Sample Mass',
        value=NominalReal(nominal=0.1, units='g'),
        template=tmpl["Expected Sample Mass"],
        origin="specified"
    ))
    flour_content.spec.conditions.append(Condition(
        name='Sample Mass',
        value=NominalReal(
            nominal=100,
            units='mg'
        ),
        template=tmpl["Sample Mass"],
        origin="specified"
    ))
    flour_content.spec.parameters.append(Parameter(
        name='Expected Sample Mass',
        value=NominalReal(nominal=0.1, units='g'),
        template=tmpl["Expected Sample Mass"],
        origin="specified"
    ))

    salt_content.properties.append(Property(
        name="Composition",
        value=EmpiricalFormula(formula="NaClCa0.006Si0.006O0.018K0.000015I0.000015"),
        template=tmpl["Chemical Formula"],
        origin="measured"
    ))
    salt_content.conditions.append(Condition(
        name='Sample Mass',
        value=NormalReal(
            mean=99 + 2 * random.random(),
            std=1.5,
            units='mg'
        ),
        template=tmpl["Sample Mass"],
        origin="measured"
    ))
    salt_content.parameters.append(Parameter(
        name='Expected Sample Mass',
        value=NominalReal(nominal=0.1, units='g'),
        template=tmpl["Expected Sample Mass"],
        origin="specified"
    ))
    salt_content.spec.conditions.append(Condition(
        name='Sample Mass',
        value=NominalReal(
            nominal=100,
            units='mg'
        ),
        template=tmpl["Sample Mass"],
        origin="specified"
    ))

    sugar_content.properties.append(Property(
        name="Composition",
        value=EmpiricalFormula(formula='C11.996H21.995O10.997S0.00015'),
        template=tmpl["Chemical Formula"],
        origin="measured"
    ))
    sugar_content.conditions.append(Condition(
        name='Sample Mass',
        value=NormalReal(
            mean=99 + 2 * random.random(),
            std=1.5,
            units='mg'
        ),
        template=tmpl["Sample Mass"],
        origin="measured"
    ))
    sugar_content.spec.parameters.append(Parameter(
        name='Expected Sample Mass',
        value=NominalReal(nominal=0.1, units='g'),
        template=tmpl["Expected Sample Mass"],
        origin="specified"
    ))

    # Code to generate quasi-repeatable run annotations
    # Note there are potential machine dependencies
    md5 = hashlib.md5()
    for x in random.getstate()[1]:
        md5.update(struct.pack(">I", x))
    run_key = md5.hexdigest()

    # Crawl tree and annotate with uids; only add ids if there's nothing there
    def _make_disambiguator():
        """Generate a closure to post-annotate for disambiguation."""
        count = dict()

        def _disambiguator(name):
            """Add a number to the name if you've seen it more than once."""
            if name in count:
                count[name] = count[name] + 1
                return "{}-{}".format(name, count[name])
            else:
                count[name] = 1
                return name

        return _disambiguator

    _disambig = _make_disambiguator()
    recursive_foreach(
        cake,
        lambda obj: obj.uids or obj.add_uid(DEMO_SCOPE, _disambig(obj.name) + run_key)
    )

    cake.notes = cake.notes + "; Très délicieux! 😀"
    cake.file_links = [FileLink(
        filename="Photo",
        url='https://www.landolakes.com/RecipeManagementSystem/media/'
            'Recipe-Media-Files/Recipes/Retail/x17/16730-beckys-butter-cake-600x600.jpg?ext=.jpg'
    )]

    return cake


if __name__ == "__main__":
    encoder = GEMDJson()
    cake = make_cake(seed=42)

    with open("example_gemd_material_history.json", "w") as f:
        context_list = complete_material_history(cake)
        f.write(json.dumps(context_list, indent=2))

    with open("example_gemd_material_template.json", "w") as f:
        f.write(encoder.thin_dumps(cake.template, indent=2))

    with open("example_gemd_process_template.json", "w") as f:
        f.write(
            encoder.thin_dumps(cake.process.ingredients[0].material.process.template, indent=2))

    with open("example_gemd_measurement_template.json", "w") as f:
        f.write(encoder.thin_dumps(cake.measurements[0].template, indent=2))

    with open("example_gemd_material_spec.json", "w") as f:
        f.write(encoder.thin_dumps(cake.spec, indent=2))

    with open("example_gemd_process_spec.json", "w") as f:
        f.write(encoder.thin_dumps(cake.process.spec, indent=2))

    with open("example_gemd_ingredient_spec.json", "w") as f:
        f.write(encoder.thin_dumps(cake.process.spec.ingredients[0], indent=2))

    with open("example_gemd_measurement_spec.json", "w") as f:
        f.write(encoder.thin_dumps(cake.measurements[0].spec, indent=2))

    with open("example_gemd_material_run.json", "w") as f:
        f.write(encoder.thin_dumps(cake, indent=2))

    with open("example_gemd_process_run.json", "w") as f:
        f.write(encoder.thin_dumps(cake.process, indent=2))

    with open("example_gemd_ingredient_run.json", "w") as f:
        f.write(encoder.thin_dumps(cake.process.ingredients[0], indent=2))

    with open("example_gemd_measurement_run.json", "w") as f:
        f.write(encoder.thin_dumps(cake.measurements[0], indent=2))
