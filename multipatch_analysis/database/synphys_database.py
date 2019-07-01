from sqlalchemy.orm import aliased
from .database import Database


class SynphysDatabase(Database):
    """Augments the Database class with convenience methods for querying the synphys database.
    """
    # database version should be incremented whenever the schema has changed
    db_version = 12
    
    default_sample_rate = 20000
    _sample_rate_str = '%dkHz' % (default_sample_rate // 1000)

    def __init__(self, ro_host, rw_host, db_name):
        from .schema import ORMBase
        Database.__init__(self, ro_host, rw_host, db_name, ORMBase)
        
    def slice_from_timestamp(self, ts, session=None):
        session = session or self.default_session
        slices = session.query(self.Slice).filter(self.Slice.acq_timestamp==ts).all()
        if len(slices) == 0:
            raise KeyError("No slice found for timestamp %0.3f" % ts)
        elif len(slices) > 1:
            raise KeyError("Multiple slices found for timestamp %0.3f" % ts)
        
        return slices[0]

    def experiment_from_timestamp(self, ts, session=None):
        session = session or self.default_session
        expts = session.query(self.Experiment).filter(self.Experiment.acq_timestamp==ts).all()
        if len(expts) == 0:
            # For backward compatibility, check for timestamp truncated to 2 decimal places
            for expt in session.query(self.Experiment).all():
                if abs((expt.acq_timestamp - ts)) < 0.01:
                    return expt
            
            raise KeyError("No experiment found for timestamp %0.3f" % ts)
        elif len(expts) > 1:
            raise RuntimeError("Multiple experiments found for timestamp %0.3f" % ts)
        
        return expts[0]

    def experiment_from_uid(self, uid, session=None):
        session = session or self.default_session
        expts = session.query(self.Experiment).filter(self.Experiment.ext_id==uid).all()
        if len(expts) == 0:
            raise KeyError('No experiment found for uid %s' %uid)
        elif len(expts) > 1:
            raise RuntimeError("Multiple experiments found for uid %s" %uid)

        return expts[0]

    def list_experiments(self, session=None):
        session = session or self.default_session
        return session.query(self.Experiment).all()

    def pair_query(self, pre_class=None, post_class=None, synapse=None, electrical=None, project_name=None, acsf=None, age=None, species=None, distance=None, internal=None, session=None):
        """Generate a query for selecting pairs from the database.

        Parameters
        ----------
        pre_class : CellClass | None
            Filter for pairs where the presynaptic cell belongs to this class
        post_class : CellClass | None
            Filter for pairs where the postsynaptic cell belongs to this class
        synapse : bool | None
            Include only pairs that are (or are not) connected by a chemical synapse
        electrical : bool | None
            Include only pairs that are (or are not) connected by an electrical synapse (gap junction)
        project_name : str | list | None
            Value(s) to match from experiment.project_name (e.g. "mouse V1 coarse matrix" or "human coarse matrix")
        acsf : str | list | None
            Filter for ACSF recipe name(s)
        age : tuple | None
            (min, max) age ranges to filter for. Either limit may be None to disable
            that check.
        species : str | None
            Species ('mouse' or 'human') to filter for
        distance : tuple | None
            (min, max) intersomatic distance in meters
        internal : str | list | None
            Electrode internal solution recipe name(s)
        
        """
        session = session or self.default_session
        pre_cell = aliased(self.Cell, name='pre_cell')
        post_cell = aliased(self.Cell, name='post_cell')
        pre_morphology = aliased(self.Morphology, name='pre_morphology')
        post_morphology = aliased(self.Morphology, name='post_morphology')
        query = session.query(
            self.Pair,
            # pre_cell,
            # post_cell,
            # pre_morphology,
            # post_morphology,
            # Experiment,
            # ConnectionStrength,
        )
        query = query.join(pre_cell, pre_cell.id==self.Pair.pre_cell_id)
        query = query.join(post_cell, post_cell.id==self.Pair.post_cell_id)
        query = query.join(pre_morphology, pre_morphology.cell_id==pre_cell.id)
        query = query.join(post_morphology, post_morphology.cell_id==post_cell.id)
        query = query.join(self.Experiment, self.Pair.experiment_id==self.Experiment.id)
        query = query.outerjoin(self.Slice, self.Experiment.slice_id==self.Slice.id) ## don't want to drop all pairs if we don't have slice or connection strength entries
        query = query.outerjoin(self.ConnectionStrength)

        if pre_class is not None:
            query = pre_class.filter_query(query, pre_cell)

        if post_class is not None:
            query = post_class.filter_query(query, post_cell)

        if synapse is not None:
            query = query.filter(self.Pair.synapse==synapse)

        if electrical is not None:
            query = query.filter(self.Pair.electrical==electrical)

        if project_name is not None:
            if isinstance(project_name, str):
                query = query.filter(self.Experiment.project_name==project_name)
            else:
                query = query.filter(self.Experiment.project_name.in_(project_name))

        if acsf is not None:
            if isinstance(acsf, str):
                query = query.filter(self.Experiment.acsf==acsf)
            else:
                query = query.filter(self.Experiment.acsf.in_(acsf))

        if age is not None:
            if age[0] is not None:
                query = query.filter(self.Slice.age>=age[0])
            if age[1] is not None:
                query = query.filter(self.Slice.age<=age[1])

        if distance is not None:
            if distance[0] is not None:
                query = query.filter(self.Pair.distance>=distance[0])
            if distance[1] is not None:
                query = query.filter(self.Pair.distance<=distance[1])

        if species is not None:
            query = query.filter(self.Slice.species==species)

        if internal is not None:
            if isinstance(internal, str):
                query = query.filter(self.Experiment.internal==internal)
            else:
                query = query.filter(self.Experiment.internal.in_(internal))

        return query
        
    def __getstate__(self):
        """Allows DB to be pickled and passed to subprocesses.
        """
        return {
            'ro_host': self.ro_host, 
            'rw_host': self.rw_host, 
            'db_name': self.db_name,
        }

    def __setstate__(self, state):
        self.__init__(ro_host=state['ro_host'], rw_host=state['rw_host'], db_name=state['db_name'])