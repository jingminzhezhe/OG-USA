'''
------------------------------------------------------------------------
Last updated 8/7/2014

Functions for generating omega, the T x S x J array which describes the
demographics of the population

This py-file calls the following other file(s):
            data\demographic\demographic_data.csv
            data\demographic\mortality_rates.csv
------------------------------------------------------------------------
'''

'''
------------------------------------------------------------------------
    Packages
------------------------------------------------------------------------
'''

import numpy as np
import pandas as pd
import numpy.polynomial.polynomial as poly

'''
------------------------------------------------------------------------
    Import data sets
------------------------------------------------------------------------
Population data:
    Obtained from:
        Annual Estimates of the Resident Population by Single Year of
            Age and Sex: April 1, 2010 to July 1, 2013
             (Both sexes)
        National Characteristics, Vintage 2013
        US Census Bureau
        http://www.census.gov/popest/data/national/asrh/2013/index.html
Mortality rates data:
    Obtained from:
        Male and Female death probabilities
        Actuarial Life table, 2010
        Social Security Administration
        http://www.ssa.gov/oact/STATS/table4c6.html
Fertility rates data:
    Obtained from:
        Births and birth rates, by age of mother, US, 2012
        National Vital Statistics Reports, CDC
        http://www.cdc.gov/nchs/data/nvsr/nvsr63/nvsr63_02.pdf
        Since rates are per 1000 women, the data is divided by 1000
------------------------------------------------------------------------
'''

# Population data
data = pd.read_table('data/demographic/demographic_data.csv', sep=',')
data = data.set_index('Age')
# Remove commas in the data
for index, value in enumerate(data['2010']):
    data['2010'][index] = int(value.replace(',', ''))
for index, value in enumerate(data['2011']):
    data['2011'][index] = int(value.replace(',', ''))
for index, value in enumerate(data['2012']):
    data['2012'][index] = int(value.replace(',', ''))
for index, value in enumerate(data['2013']):
    data['2013'][index] = int(value.replace(',', ''))
data_raw = data.copy(deep=True)
data = data[16:76]

# Mortality rates data
mort_data = pd.read_table('data/demographic/mortality_rates.csv', sep=',')
# Average male and female death rates
mort_data['mort_rate'] = (
    mort_data.prob_live_next_male + mort_data.prob_live_next_female) / 2
del mort_data['prob_live_next_female'], mort_data['prob_live_next_male']
# As the data gives the probability of death, one minus the rate will
# give the survial rate
mort_data['surv_rate'] = 1 - mort_data.mort_rate
# Create an array of death rates of children
children_rate = np.array(mort_data[(mort_data.age < 15)].surv_rate)

# Fertility rates data
fert_data = np.array(
    [.3, 26.6, 12.3, 47.3, 81.2, 106.2, 98.7, 49.6, 10.5, .8]) / 1000
# Fertility rates are given in age groups of 5 years, so the following
# are the midpoints of those groups
age_midpoint = np.array([12, 17, 16, 18.5, 22, 27, 32, 37, 42, 49.5])

'''
------------------------------------------------------------------------
    Survival Rates
------------------------------------------------------------------------
'''


def get_survival(S, J):
    '''
    Parameters:
        S - Number of age cohorts
        J - Number of ability types

    Returns:
        surv_array - S x J array of survival rates for each age cohort
    '''
    # Fit a polynomial to the data of survival rates (so that we are not
    # bound to groups that span at least a year
    poly_surv = poly.polyfit(mort_data.age, mort_data.surv_rate, deg=10)
    # Evaluate the polynomial every year for individuals 15 to 75
    survival_rate = poly.polyval(np.linspace(15, 75, 60), poly_surv)
    for i in xrange(survival_rate.shape[0]):
        if survival_rate[i] > 1.0:
            survival_rate[i] = 1.0
    surv_rate_condensed = np.zeros(S)
    # If S < 60, then group years together
    for s in xrange(S):
        surv_rate_condensed[s] = np.product(
            survival_rate[s*(60/S):(s+1)*(60/S)])
    # All individuals must die if they reach the last age group
    surv_rate_condensed[-1] = 0
    surv_array = np.tile(surv_rate_condensed.reshape(S, 1), (1, J))
    return surv_array

'''
------------------------------------------------------------------------
    Immigration Rates
------------------------------------------------------------------------
'''


def get_immigration(S, J):
    '''
    Parameters:
        S - Number of age cohorts
        J - Number of ability types

    Returns:
        im_array - (S-1) x J array of immigration rates for each
                   age cohort
    '''
    pop_2010, pop_2011 = np.array(data_raw['2010'], dtype='f'), np.array(
        data_raw['2011'], dtype='f')
    # Get survival rates for the S age groups
    surv_array = get_survival(60, 1)
    surv_array = np.array(list(children_rate) + list(surv_array))
    # Only keep track of individuals in 2010 that don't die
    pop_2010 = pop_2010[1:76] * surv_array
    # In 2011, individuals will have aged one year
    pop_2011 = pop_2011[2:77]
    # The immigration rate will be 1 plus the percent change in
    # population (since death has already been accounted for)
    perc_change = ((pop_2011 - pop_2010) / pop_2010) + 1.0
    # Remove the last entry, since individuals in the last period will die
    perc_change = perc_change[:-1]
    # Fit a polynomial to the immigration rates
    poly_imm = poly.polyfit(np.linspace(1, 75, 74), perc_change, deg=10)
    im_array = poly.polyval(np.linspace(1, 75, 74), poly_imm)
    im_array2 = im_array[15:76]
    imm_rate_condensed = np.zeros(S-1)
    # If S < 60, then group years together
    for s in xrange(S-1):
        imm_rate_condensed[s] = np.product(
            im_array2[s*(60/S):(s+1)*(60/S)])
    im_array2 = np.tile(imm_rate_condensed.reshape(S-1, 1), (1, J))
    children_im = im_array[0:14]
    return im_array2, children_im


'''
------------------------------------------------------------------------
    Fertility Rates
------------------------------------------------------------------------
'''


def get_fert(S, J):
    '''
    Parameters:
        S - Number of age cohorts
        J - Number of ability types

    Returns:
        fert_rate - S x J array of fertility rates for each age cohort
        children  - 15 x J array of zeros, to be used in get_omega()
    '''
    # Fit a polynomial to the fertility rates
    poly_fert = poly.polyfit(age_midpoint, fert_data, deg=4)
    fert_rate = poly.polyval(np.linspace(15, 75, 60), poly_fert)
    # Do not allow negative fertility rates, or nonzero rates outside of
    # a certain age range
    for i in xrange(60):
        if np.linspace(15, 75, 60)[i] > 50 or np.linspace(15, 75, 60)[i] < 10:
            fert_rate[i] = 0
        if fert_rate[i] < 0:
            fert_rate[i] = 0
    fert_rate_condensed = np.zeros(S)
    # If S < 60, then group years together
    for s in xrange(S):
        fert_rate_condensed[s] = np.mean(
            fert_rate[s*(60/S):(s+1)*(60/S)])
    fert_rate = np.tile(fert_rate_condensed.reshape(S, 1), (1, J))
    # Divide the fertility rate by 2, since it will be used for men and women
    fert_rate /= 2.0
    children = np.zeros((15, J))
    return fert_rate, children

'''
------------------------------------------------------------------------
    Generate Omega array
------------------------------------------------------------------------
'''


def get_omega(S, J, T):
    '''
    Parameters:
        S - Number of age cohorts
        J - Number of ability types

    Returns:

    '''
    age_groups = np.linspace(16, 76, S+1)
    # Generate list of total population size for 2010, 2011, 2012 and 2013
    sums = [sum2010, sum2011, sum2012, sum2013] = [
        data['2010'].values.sum(), data['2011'].values.sum(), data[
            '2012'].values.sum(), data['2013'].values.sum()]
    # For each year of the data, transform each age group's population to
    # be a fraction of the total
    data['2010'] /= float(sum2010)
    data['2011'] /= float(sum2011)
    data['2012'] /= float(sum2012)
    data['2013'] /= float(sum2013)
    omega = data['2010'].values
    new_omega = np.zeros(S)
    for ind in xrange(S):
        new_omega[ind] = (data[
            np.array((age_groups[ind] <= data.index)) & np.array(
                (data.index < age_groups[ind+1]))])['2010'].values.sum()
    new_omega = np.tile(new_omega.reshape(S, 1), (1, J))
    # Each ability group contains 1/J fraction of age group
    new_omega /= J
    surv_array = get_survival(S, J)
    imm_array, children_im = get_immigration(S, J)
    omega_big = np.tile(new_omega.reshape(1, S, J), (T, 1, 1))
    fert_rate, children = get_fert(S, J)
    # Keep track of how many individuals have been born and their survival
    # until they enter the working population
    for ind in xrange(15):
        children[ind, :] = (
            omega_big[0, :, :] * fert_rate).sum(0) * np.prod(
            children_rate[:ind]) * np.prod(children_im[:ind])
    # Generate the time path for each age/abilty group
    for t in xrange(1, T):
        omega_big[t, 0, :] = children[-1, :] * children_rate[-1] * imm_array[0]
        omega_big[t, 1:, :] = omega_big[t-1, :-1, :] * surv_array[
            :-1].reshape(1, S-1, J) * imm_array.reshape(1, S-1, J)
        children[1:, :] = children[:-1, :] * children_rate[:-1].reshape(
            14, 1) * children_im.reshape(14, 1)
        children[0, :] = (omega_big[t, :, :] * fert_rate).sum(0)
    return omega_big

# Known problems
# Fitted polynomial on survival rates creates some entries that are greater than 1